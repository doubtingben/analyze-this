import 'dotenv/config';
import OpenAI from 'openai';
import { Client } from 'irc-framework';
import { buildMcpToolRegistry } from './mcp.js';
import { exec } from 'child_process';
import { promisify } from 'util';
const execAsync = promisify(exec);
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
if (!OPENROUTER_API_KEY) {
    throw new Error("OPENROUTER_API_KEY is required");
}
const OPENROUTER_MODEL = process.env.OPENROUTER_MODEL || "google/gemini-2.0-flash-exp:free";
const OPENROUTER_BASE_URL = process.env.OPENROUTER_BASE_URL || "https://openrouter.ai/api/v1";
const OPENROUTER_SITE_URL = process.env.OPENROUTER_SITE_URL || "";
const OPENROUTER_APP_NAME = process.env.OPENROUTER_APP_NAME || "analyze-this-agent";
const llm = new OpenAI({
    apiKey: OPENROUTER_API_KEY,
    baseURL: OPENROUTER_BASE_URL,
    defaultHeaders: {
        ...(OPENROUTER_SITE_URL ? { "HTTP-Referer": OPENROUTER_SITE_URL } : {}),
        "X-Title": OPENROUTER_APP_NAME,
    },
});
// IRC Configuration
const IRC_SERVER = process.env.IRC_SERVER || 'chat.interestedparticipant.org';
const IRC_PORT = parseInt(process.env.IRC_PORT || '6697');
const IRC_NICK = process.env.IRC_NICK || 'AnalyzeBot';
const IRC_CHANNEL = process.env.IRC_CHANNEL || '#analyze-this';
async function run() {
    console.log('Starting AnalyzeBot...');
    // Initialize MCP Tools from configured servers
    let registry = {
        tools: [],
        callTool: async (_name, _args) => {
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
                        git_origin: {
                            type: "string",
                            description: "The git remote name to fetch from. Defaults to 'origin'.",
                        }
                    }
                }
            }
        });
        registry.tools.push({
            type: "function",
            function: {
                name: "get_app_version",
                description: "Get the currently deployed application version by checking both the local repository's checkout state and the running backend application API.",
                parameters: {
                    type: "object",
                    properties: {}
                }
            }
        });
        const originalCallTool = registry.callTool;
        registry.callTool = async (name, args) => {
            if (name === "update_app") {
                const gitRef = args.git_ref || "main";
                const gitOrigin = args.git_origin || "origin";
                try {
                    const workspaceDir = process.cwd(); // Assume agent runs in app root or similar context, but we will use the git repo path we're in
                    console.log(`Starting app update... Fetching ${gitOrigin}, checking out ${gitRef}`);
                    const command = [
                        `git fetch ${gitOrigin}`,
                        `git checkout ${gitRef}`,
                        `git pull ${gitOrigin} ${gitRef} || true`, // ignore pull error if it's a detached commit
                        `sudo nixos-rebuild switch --flake .#nixos-analyze-this`
                    ].join(' && ');
                    console.log(`Executing: ${command}`);
                    const { stdout, stderr } = await execAsync(command);
                    console.log(`Update stdout: ${stdout}`);
                    if (stderr)
                        console.error(`Update stderr: ${stderr}`);
                    return {
                        status: "success",
                        message: `Successfully updated app to ${gitRef} from ${gitOrigin}.`,
                        stdout,
                        stderr
                    };
                }
                catch (error) {
                    console.error("App update failed:", error);
                    return {
                        status: "error",
                        message: `Failed to update app: ${error.message}`,
                        stdout: error.stdout,
                        stderr: error.stderr
                    };
                }
            }
            if (name === "get_app_version") {
                try {
                    let gitInfo = "Unknown Git State";
                    try {
                        const { stdout } = await execAsync('git log -1 --format="Commit: %H%nMessage: %s"');
                        gitInfo = stdout.trim();
                    }
                    catch (e) {
                        console.error("Git log failed:", e.message);
                    }
                    let apiVersion = "Unknown API Version";
                    try {
                        const response = await fetch("http://127.0.0.1:8000/api/version");
                        if (response.ok) {
                            const data = await response.json();
                            apiVersion = data.version;
                        }
                        else {
                            apiVersion = `HTTP ${response.status}`;
                        }
                    }
                    catch (e) {
                        console.error("Failed to fetch API version:", e.message);
                    }
                    return {
                        status: "success",
                        deployed_api_version: apiVersion,
                        local_checkout_info: gitInfo
                    };
                }
                catch (error) {
                    return {
                        status: "error",
                        message: `Failed to get app version: ${error.message}`
                    };
                }
            }
            return originalCallTool(name, args);
        };
        console.log(`Loaded ${registry.tools.length} total tools from MCP servers and local agents.`);
    }
    catch (error) {
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
    const channelHistory = [];
    client.on('message', async (event) => {
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
                }
                catch (err) {
                    console.error('Error generating response:', err);
                    client.say(IRC_CHANNEL, `${nick}: Sorry, I encountered an error processing your request.`);
                }
            }
        }
    });
    client.on('error', (err) => {
        // console.error('IRC Error:', err);
    });
}
async function generateReply(prompt, tools, callTool, history = []) {
    const historyText = history.map(h => `<${h.nick}> ${h.message}`).join('\n');
    const systemPrompt = `You are AnalyzeBot. Keep responses concise and useful in IRC. Use tools when needed. You can manage deployments and check the current app version using your tools.\n\n` +
        `Here is the recent channel history for context:\n` +
        (historyText ? historyText : "(no history yet)") + `\n\n` +
        `If the channel history is missing or incomplete for you to understand the context, it's ok to ask the user for additional context.`;
    const messages = [
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
            model: OPENROUTER_MODEL,
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
                let result;
                try {
                    result = await callTool(toolCall.function.name, args);
                }
                catch (error) {
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
function safeParseJson(value) {
    try {
        return value ? JSON.parse(value) : {};
    }
    catch {
        return {};
    }
}
run().catch(console.error);
