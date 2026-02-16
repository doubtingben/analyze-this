import 'dotenv/config';
import { genkit } from 'genkit';
import { googleAI } from '@genkit-ai/googleai';
import { Client } from 'irc-framework';
import { getMcpTools } from './mcp.js';
// Configure Genkit
const ai = genkit({
    plugins: [googleAI()],
    model: googleAI.model("gemini-2.5-flash"),
});
// IRC Configuration
const IRC_SERVER = process.env.IRC_SERVER || 'chat.interestedparticipant.org';
const IRC_PORT = parseInt(process.env.IRC_PORT || '6697');
const IRC_NICK = process.env.IRC_NICK || 'AnalyzeBot';
const IRC_CHANNEL = process.env.IRC_CHANNEL || '#analyze-this';
async function run() {
    console.log('Starting AnalyzeBot...');
    // Initialize MCP Tools from configured servers
    let tools = [];
    try {
        tools = await getMcpTools(ai);
        console.log(`Loaded ${tools.length} total tools from MCP servers.`);
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
    client.on('message', async (event) => {
        if (event.target === IRC_CHANNEL) {
            const message = event.message;
            const nick = event.nick;
            if (message.startsWith(`${IRC_NICK}:`) || message.includes(IRC_NICK)) {
                const query = message.replace(`${IRC_NICK}:`, '').trim();
                console.log(`Received query from ${nick}: ${query}`);
                try {
                    const { text } = await ai.generate({
                        prompt: query,
                        tools: tools,
                        config: {
                            temperature: 0.7,
                        },
                    });
                    client.say(IRC_CHANNEL, `${nick}: ${text}`);
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
run().catch(console.error);
