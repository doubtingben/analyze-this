import 'dotenv/config';
import OpenAI from 'openai';
import { Client } from 'irc-framework';
import { buildMcpToolRegistry } from './mcp.js';
import type { McpToolRegistry } from './mcp.js';
import { exec, execFile } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);
const execFileAsync = promisify(execFile);

const OPENAI_API_KEY = process.env.OPENAI_API_KEY || process.env.OPENROUTER_API_KEY || "ollama";

const OPENAI_MODEL = process.env.OPENAI_MODEL || process.env.OPENROUTER_MODEL || "gemma4:31b";
const OPENAI_BASE_URL = process.env.OPENAI_BASE_URL || process.env.OPENROUTER_BASE_URL || "http://nixos-gpt:11434/v1";
const APP_SITE_URL = process.env.APP_SITE_URL || process.env.OPENROUTER_SITE_URL || "";
const APP_NAME = process.env.APP_NAME || process.env.OPENROUTER_APP_NAME || "analyze-this-agent";

const llm = new OpenAI({
    apiKey: OPENAI_API_KEY,
    baseURL: OPENAI_BASE_URL,
    defaultHeaders: {
        ...(APP_SITE_URL ? { "HTTP-Referer": APP_SITE_URL } : {}),
        "X-Title": APP_NAME,
    },
});

// IRC Configuration
const IRC_SERVER = process.env.IRC_SERVER || 'chat.interestedparticipant.org';
const IRC_PORT = parseInt(process.env.IRC_PORT || '6697');
const IRC_NICK = process.env.IRC_NICK || 'AnalyzeBot';
const IRC_CHANNEL = process.env.IRC_CHANNEL || '#analyze-this';

const LOG_TARGET_UNITS = {
    backend: ['analyze-backend.service'],
    worker: [
        'worker-manager.service',
        'worker-analysis.service',
        'worker-normalization.service',
        'worker-follow-up.service',
        'worker-podcast-audio.service',
    ],
    worker_manager: ['worker-manager.service'],
    worker_analysis: ['worker-analysis.service'],
    worker_normalization: ['worker-normalization.service'],
    worker_follow_up: ['worker-follow-up.service'],
    worker_podcast_audio: ['worker-podcast-audio.service'],
} as const;

type LogTarget = keyof typeof LOG_TARGET_UNITS;

function isLogTarget(value: string): value is LogTarget {
    return Object.prototype.hasOwnProperty.call(LOG_TARGET_UNITS, value);
}

function validateLogLines(value: unknown): number {
    const parsed = Number(value ?? 100);
    if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed < 1) {
        throw new Error("lines must be a positive integer");
    }
    if (parsed > 500) {
        throw new Error("lines must be 500 or less");
    }
    return parsed;
}

async function getServiceLogs(args: Record<string, any>) {
    const target = args.target;
    if (typeof target !== "string" || !isLogTarget(target)) {
        throw new Error(`target must be one of: ${Object.keys(LOG_TARGET_UNITS).join(", ")}`);
    }

    const lines = validateLogLines(args.lines);
    const since = typeof args.since === "string" && args.since.trim() ? args.since.trim() : "1 hour ago";
    const grep = typeof args.grep === "string" && args.grep.trim() ? args.grep.trim() : undefined;
    const units = LOG_TARGET_UNITS[target];

    const journalctlArgs = [
        "--no-pager",
        "--output=short-iso",
        "--since",
        since,
        "-n",
        String(lines),
        ...units.flatMap((unit) => ["-u", unit]),
    ];

    if (grep) {
        journalctlArgs.push("--grep", grep);
    }

    try {
        const { stdout, stderr } = await execFileAsync("journalctl", journalctlArgs, {
            maxBuffer: 1024 * 1024,
        });
        const trimmedStdout = stdout.trim();
        const trimmedStderr = stderr.trim();

        return {
            status: "success",
            target,
            units,
            effective_since: since,
            effective_lines: lines,
            grep: grep || null,
            logs: trimmedStdout || "No entries found.",
            stderr: trimmedStderr || undefined,
        };
    } catch (error: any) {
        const stdout = typeof error?.stdout === "string" ? error.stdout.trim() : "";
        const stderr = typeof error?.stderr === "string" ? error.stderr.trim() : "";
        if ((error?.code === 1 || error?.code === undefined) && !stdout) {
            return {
                status: "success",
                target,
                units,
                effective_since: since,
                effective_lines: lines,
                grep: grep || null,
                logs: "No entries found.",
                stderr: stderr || undefined,
            };
        }

        throw new Error(stderr || stdout || error?.message || "journalctl failed");
    }
}

async function run() {
    console.log('Starting AnalyzeBot...');

    // Initialize MCP Tools from configured servers
    let registry: McpToolRegistry = {
        tools: [],
        callTool: async (_name: string, _args: Record<string, any>) => {
            throw new Error("MCP tool registry unavailable");
        },
    };
    try {
        registry = await buildMcpToolRegistry();
        
        // Add local app update tool
        registry.tools.push({
            type: "function",
            function: {
                name: "update_app",
                description: "Update the AnalyzeThis application by pulling from git and running the Nix deployment command. Use this when you are asked to deploy or update the app.",
                parameters: {
                    type: "object",
                    properties: {
                        git_ref: {
                            type: "string",
                            description: "The git branch or commit to deploy. Defaults to 'main'.",
                        },
                        git_repo_url: {
                            type: "string",
                            description: "The git repository URL to fetch from. Defaults to 'https://github.com/doubtingben/analyze-this.git'.",
                        }
                    }
                }
            }
        });

        registry.tools.push({
            type: "function",
            function: {
                name: "get_app_version",
                description: "Get the currently deployed application API version and check the latest remote commit on a given repository.",
                parameters: {
                    type: "object",
                    properties: {
                        git_repo_url: {
                            type: "string",
                            description: "The git repository URL to check. Defaults to 'https://github.com/doubtingben/analyze-this.git'.",
                        },
                        git_ref: {
                            type: "string",
                            description: "The git branch or commit to check. Defaults to 'HEAD'.",
                        }
                    }
                }
            }
        });

        registry.tools.push({
            type: "function",
            function: {
                name: "get_service_logs",
                description: "Read recent journald logs for the backend or worker services on this host. Use this to inspect runtime failures, worker errors, or recent backend behavior.",
                parameters: {
                    type: "object",
                    properties: {
                        target: {
                            type: "string",
                            enum: Object.keys(LOG_TARGET_UNITS),
                            description: "Which service logs to read. Use 'worker' for all worker-related units, or a specific worker target for one unit.",
                        },
                        lines: {
                            type: "integer",
                            description: "How many recent log lines to return. Default 100, maximum 500.",
                            default: 100,
                            minimum: 1,
                            maximum: 500,
                        },
                        since: {
                            type: "string",
                            description: "Journald-compatible lower time bound such as '15 minutes ago' or '1 hour ago'. Defaults to '1 hour ago'.",
                        },
                        grep: {
                            type: "string",
                            description: "Optional journalctl grep pattern to filter matching log messages.",
                        }
                    },
                    required: ["target"]
                }
            }
        });

        const originalCallTool = registry.callTool;
        registry.callTool = async (name: string, args: Record<string, any>) => {
            if (name === "update_app") {
                const gitRef = args.git_ref || "main";
                const gitRepoUrl = args.git_repo_url || "https://github.com/doubtingben/analyze-this.git";
                
                let tempDir = "";
                try {
                    console.log(`Starting app update... Cloning ${gitRepoUrl}, checking out ${gitRef}`);
                    
                    // 1. Create a temp directory
                    const mktempResult = await execAsync('mktemp -d');
                    tempDir = mktempResult.stdout.trim();

                    // 2. Clone the repository into it
                    await execAsync(`git clone ${gitRepoUrl} ${tempDir}`);

                    // 3. Checkout target ref and pull if branch
                    await execAsync(`cd ${tempDir} && git fetch origin && git checkout ${gitRef} && git pull origin ${gitRef} || true`);
                    
                    // 4. Run Nix deployment
                    const command = `cd ${tempDir} && sudo nixos-rebuild switch --flake .#nixos-analyze-this`;
                    console.log(`Executing: ${command}`);
                    const { stdout, stderr } = await execAsync(command);
                    console.log(`Update stdout: ${stdout}`);
                    if (stderr) console.error(`Update stderr: ${stderr}`);

                    // 5. Cleanup temp directory is handled in the finally block

                    return { 
                        status: "success", 
                        message: `Successfully updated app to ${gitRef} from ${gitRepoUrl}.`,
                        stdout,
                        stderr
                    };
                } catch (error: any) {
                    console.error("App update failed:", error);
                    return { 
                        status: "error", 
                        message: `Failed to update app: ${error.message}`,
                        stdout: error.stdout,
                        stderr: error.stderr 
                    };
                } finally {
                    if (tempDir) {
                        try {
                            await execAsync(`rm -rf ${tempDir}`);
                        } catch (e) {
                            console.error(`Failed to cleanup temp dir ${tempDir}:`, e);
                        }
                    }
                }
            }
            if (name === "get_app_version") {
                const gitRepoUrl = args.git_repo_url || "https://github.com/doubtingben/analyze-this.git";
                const gitRef = args.git_ref || "HEAD";

                try {
                    let gitInfo = "Unknown Git State";
                    try {
                        const { stdout } = await execAsync(`git ls-remote ${gitRepoUrl} ${gitRef}`);
                        gitInfo = stdout.trim() || `No commit found for ${gitRef}`;
                    } catch (e: any) {
                        console.error("Git ls-remote failed:", e.message);
                    }

                    let apiVersion = "Unknown API Version";
                    try {
                        const response = await fetch("http://127.0.0.1:8000/api/version");
                        if (response.ok) {
                            const data = await response.json();
                            apiVersion = data.version;
                        } else {
                            apiVersion = `HTTP ${response.status}`;
                        }
                    } catch (e: any) {
                        console.error("Failed to fetch API version:", e.message);
                    }

                    return {
                        status: "success",
                        deployed_api_version: apiVersion,
                        remote_repository_target: gitInfo
                    };
                } catch (error: any) {
                    return {
                        status: "error",
                        message: `Failed to get app version: ${error.message}`
                    };
                }
            }
            if (name === "get_service_logs") {
                return await getServiceLogs(args);
            }
            return originalCallTool(name, args);
        };

        console.log(`Loaded ${registry.tools.length} total tools from MCP servers and local agents.`);
    } catch (error) {
        console.error('Failed to load MCP tools:', error);
    }

    // Initialize IRC Client
    const client = new Client();

    client.connect({
        host: IRC_SERVER,
        port: IRC_PORT,
        nick: IRC_NICK,
        username: process.env.IRC_USERNAME || IRC_NICK,
        password: process.env.IRC_PASSWORD,
        tls: true,
        rejectUnauthorized: false,
    });

    client.on('registered', () => {
        console.log('Connected to IRC server.');
        client.join(IRC_CHANNEL);
        console.log(`Joined ${IRC_CHANNEL}`);
    });

    const MAX_HISTORY = 50;
    const channelHistory: { nick: string, message: string }[] = [];

    client.on('message', async (event: any) => {
        if (event.target === IRC_CHANNEL) {
            const message = event.message;
            const nick = event.nick;

            channelHistory.push({ nick, message });
            if (channelHistory.length > MAX_HISTORY) {
                channelHistory.shift();
            }

            if (message.startsWith(`${IRC_NICK}:`) || message.includes(IRC_NICK)) {
                const query = message.replace(`${IRC_NICK}:`, '').trim();
                console.log(`Received query from ${nick}: ${query}`);

                try {
                    const text = await generateReply(query, registry.tools, registry.callTool, channelHistory);
                    const replyText = text || "(no response)";

                    client.say(IRC_CHANNEL, `${nick}: ${replyText}`);

                    channelHistory.push({ nick: IRC_NICK, message: `${nick}: ${replyText}` });
                    if (channelHistory.length > MAX_HISTORY) {
                        channelHistory.shift();
                    }
                } catch (err) {
                    console.error('Error generating response:', err);
                    client.say(IRC_CHANNEL, `${nick}: Sorry, I encountered an error processing your request.`);
                }
            }
        }
    });

    client.on('error', (err: any) => {
        // console.error('IRC Error:', err);
    });
}

async function generateReply(
    prompt: string,
    tools: any[],
    callTool: (name: string, args: Record<string, any>) => Promise<any>,
    history: { nick: string, message: string }[] = []
): Promise<string> {
    const historyText = history.map(h => `<${h.nick}> ${h.message}`).join('\n');
    const systemPrompt = `You are AnalyzeBot. Keep responses concise and useful in IRC. Use tools when needed. You can manage deployments, check the current app version, and inspect backend and worker journald logs using your tools. The official git repository URL is 'https://github.com/doubtingben/analyze-this.git'.\n\n` +
        `Here is the recent channel history for context:\n` +
        (historyText ? historyText : "(no history yet)") + `\n\n` +
        `If the channel history is missing or incomplete for you to understand the context, it's ok to ask the user for additional context.`;

    const messages: any[] = [
        {
            role: "system",
            content: systemPrompt,
        },
        {
            role: "user",
            content: prompt,
        },
    ];

    for (let i = 0; i < 6; i++) {
        const completion = await llm.chat.completions.create({
            model: OPENAI_MODEL,
            messages,
            tools: tools.length > 0 ? tools : undefined,
            tool_choice: tools.length > 0 ? "auto" : undefined,
            temperature: 0.7,
        });

        const choice = completion.choices[0];
        const assistantMessage = choice?.message;
        if (!assistantMessage) {
            return "I couldn't generate a response.";
        }

        if (assistantMessage.tool_calls && assistantMessage.tool_calls.length > 0) {
            messages.push({
                role: "assistant",
                content: assistantMessage.content || "",
                tool_calls: assistantMessage.tool_calls,
            });

            for (const toolCall of assistantMessage.tool_calls) {
                const args = safeParseJson(toolCall.function.arguments);
                let result: any;
                try {
                    result = await callTool(toolCall.function.name, args);
                } catch (error: any) {
                    result = { error: String(error?.message || error) };
                }
                messages.push({
                    role: "tool",
                    tool_call_id: toolCall.id,
                    content: JSON.stringify(result),
                });
            }
            continue;
        }

        return assistantMessage.content || "";
    }

    return "I couldn't complete tool calls in time.";
}

function safeParseJson(value: string): Record<string, any> {
    try {
        return value ? JSON.parse(value) : {};
    } catch {
        return {};
    }
}

run().catch(console.error);
