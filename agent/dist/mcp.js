import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { z } from "genkit";
import { readFileSync } from "fs";
// Load configuration from file or environment
export function loadMcpConfig() {
    // First try loading from config file
    const configPath = process.env.MCP_CONFIG_FILE;
    if (configPath) {
        try {
            const configContent = readFileSync(configPath, "utf-8");
            return JSON.parse(configContent);
        }
        catch (error) {
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
function createTransport(config) {
    switch (config.type) {
        case "sse":
            return new SSEClientTransport(new URL(config.url));
        case "stdio":
            return new StdioClientTransport({
                command: config.command,
                args: config.args,
                env: config.env,
            });
        default:
            throw new Error(`Unknown MCP server type: ${config.type}`);
    }
}
export async function getMcpClient(config) {
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
export async function getMcpTools(ai) {
    const config = loadMcpConfig();
    const serverNames = Object.keys(config.servers);
    if (serverNames.length === 0) {
        console.warn("No MCP servers configured.");
        return [];
    }
    const allTools = [];
    const clients = [];
    for (const serverName of serverNames) {
        const serverConfig = config.servers[serverName];
        console.log(`Connecting to MCP server '${serverName}' (${serverConfig.type})...`);
        try {
            const client = await getMcpClient(serverConfig);
            clients.push(client);
            const toolsList = await client.listTools();
            console.log(`Loaded ${toolsList.tools.length} tools from '${serverName}'.`);
            const genkitTools = toolsList.tools.map((tool) => {
                // Prefix tool name with server name to avoid collisions
                const prefixedName = serverNames.length > 1
                    ? `${serverName}_${tool.name}`
                    : tool.name;
                // Workaround: Append the JSON schema to the description so the LLM knows what to pass.
                const schemaDescription = `\n\nInput Schema: ${JSON.stringify(tool.inputSchema, null, 2)}`;
                return ai.defineTool({
                    name: prefixedName,
                    description: (tool.description || "") + schemaDescription,
                    inputSchema: z.any(),
                    outputSchema: z.any(),
                }, async (input) => {
                    const result = await client.callTool({
                        name: tool.name,
                        arguments: input,
                    });
                    // MCP returns { content: [{ type: 'text', text: '...' }] } usually.
                    // Genkit expects a return value (string or object).
                    // We should parse the MCP result.
                    return result;
                });
            });
            allTools.push(...genkitTools);
        }
        catch (error) {
            console.error(`Failed to connect to MCP server '${serverName}':`, error);
        }
    }
    return allTools;
}
