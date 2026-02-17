import 'dotenv/config';
import OpenAI from 'openai';
import { Client } from 'irc-framework';
import { buildMcpToolRegistry } from './mcp.js';
import type { McpToolRegistry } from './mcp.js';

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
    let registry: McpToolRegistry = {
        tools: [],
        callTool: async (_name: string, _args: Record<string, any>) => {
            throw new Error("MCP tool registry unavailable");
        },
    };
    try {
        registry = await buildMcpToolRegistry();
        console.log(`Loaded ${registry.tools.length} total tools from MCP servers.`);
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

    client.on('message', async (event: any) => {
        if (event.target === IRC_CHANNEL) {
            const message = event.message;
            const nick = event.nick;

            if (message.startsWith(`${IRC_NICK}:`) || message.includes(IRC_NICK)) {
                const query = message.replace(`${IRC_NICK}:`, '').trim();
                console.log(`Received query from ${nick}: ${query}`);

                try {
                    const text = await generateReply(query, registry.tools, registry.callTool);

                    client.say(IRC_CHANNEL, `${nick}: ${text || "(no response)"}`);
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
): Promise<string> {
    const messages: any[] = [
        {
            role: "system",
            content: "You are AnalyzeBot. Keep responses concise and useful in IRC. Use tools when needed.",
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
