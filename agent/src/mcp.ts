import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { readFileSync } from "fs";

// MCP Server Configuration Types
export interface McpServerConfigSSE {
    type: "sse";
    url: string;
}

export interface McpServerConfigStdio {
    type: "stdio";
    command: string;
    args?: string[];
    env?: Record<string, string>;
}

export type McpServerConfig = McpServerConfigSSE | McpServerConfigStdio;

export interface McpConfig {
    servers: Record<string, McpServerConfig>;
}

// Load configuration from file or environment
export function loadMcpConfig(): McpConfig {
    // First try loading from config file
    const configPath = process.env.MCP_CONFIG_FILE;
    if (configPath) {
        try {
            const configContent = readFileSync(configPath, "utf-8");
            return JSON.parse(configContent) as McpConfig;
        } catch (error) {
            console.error(`Failed to load MCP config from ${configPath}:`, error);
        }
    }

    // Fall back to legacy single URL environment variable
    const legacyUrl = process.env.MCP_SERVER_URL;
    if (legacyUrl) {
        return {
            servers: {
                default: {
                    type: "sse",
                    url: legacyUrl,
                },
            },
        };
    }

    return { servers: {} };
}

// Create transport based on config type
function createTransport(config: McpServerConfig) {
    switch (config.type) {
        case "sse":
            return new SSEClientTransport(new URL(config.url));
        case "stdio":
            return new StdioClientTransport({
                command: config.command,
                args: config.args,
                env: {
                    ...process.env as Record<string, string>,
                    ...config.env,
                },
            });
        default:
            throw new Error(`Unknown MCP server type: ${(config as any).type}`);
    }
}

export async function getMcpClient(config: McpServerConfig): Promise<Client> {
    const transport = createTransport(config);

    const client = new Client({
        name: "genkit-client",
        version: "1.0.0",
    }, {
        capabilities: {}
    });

    await client.connect(transport);
    return client;
}

export interface OpenAIToolDef {
    type: "function";
    function: {
        name: string;
        description?: string;
        parameters: any;
    };
}

export interface McpToolRegistry {
    tools: OpenAIToolDef[];
    callTool: (name: string, args: Record<string, any>) => Promise<any>;
}

export async function buildMcpToolRegistry(): Promise<McpToolRegistry> {
    const config = loadMcpConfig();
    const serverNames = Object.keys(config.servers);

    if (serverNames.length === 0) {
        console.warn("No MCP servers configured.");
        return {
            tools: [],
            callTool: async () => {
                throw new Error("No MCP tools configured");
            },
        };
    }

    const allTools: OpenAIToolDef[] = [];
    const toolMap = new Map<string, { client: Client; mcpToolName: string }>();

    for (const serverName of serverNames) {
        const serverConfig = config.servers[serverName];
        console.log(`Connecting to MCP server '${serverName}' (${serverConfig.type})...`);

        try {
            const client = await getMcpClient(serverConfig);

            const toolsList = await client.listTools();
            console.log(`Loaded ${toolsList.tools.length} tools from '${serverName}'.`);

            const openAITools = toolsList.tools.map((tool) => {
                // Prefix tool name with server name to avoid collisions
                const prefixedName = serverNames.length > 1
                    ? `${serverName}_${tool.name}`
                    : tool.name;

                toolMap.set(prefixedName, { client, mcpToolName: tool.name });

                return {
                    type: "function",
                    function: {
                        name: prefixedName,
                        description: tool.description || "",
                        parameters: tool.inputSchema || { type: "object", properties: {} },
                    },
                } as OpenAIToolDef;
            });

            allTools.push(...openAITools);
        } catch (error) {
            console.error(`Failed to connect to MCP server '${serverName}':`, error);
        }
    }

    return {
        tools: allTools,
        callTool: async (name: string, args: Record<string, any>) => {
            const tool = toolMap.get(name);
            if (!tool) {
                throw new Error(`Unknown tool: ${name}`);
            }
            return tool.client.callTool({
                name: tool.mcpToolName,
                arguments: args,
            });
        },
    };
}
