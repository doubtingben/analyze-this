#!/usr/bin/env node

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const readline = require('readline');

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

const RED = '\x1b[31m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const CYAN = '\x1b[36m';
const RESET = '\x1b[0m';

function log(color, message) {
    console.log(`${color}${message}${RESET}`);
}

function runCommand(command) {
    try {
        return execSync(command, { encoding: 'utf8', stdio: 'pipe' }).trim();
    } catch (error) {
        return null;
    }
}

function checkRequirement(name, command) {
    process.stdout.write(`Checking for ${name}... `);
    const result = runCommand(command);
    if (result) {
        console.log(`${GREEN}Found${RESET}`);
        return true;
    } else {
        console.log(`${RED}Not Found${RESET}`);
        return false;
    }
}

const ANDROID_SDK_ROOT = process.env.ANDROID_HOME || process.env.ANDROID_SDK_ROOT;

async function setupAndroid() {
    log(CYAN, '\n=== Android Setup ===');

    if (!ANDROID_SDK_ROOT) {
        log(RED, 'ANDROID_HOME or ANDROID_SDK_ROOT environment variable is not set.');
        log(YELLOW, 'Please install Android Studio and set up the SDK.');
        return;
    }

    const hasAdb = checkRequirement('adb', 'adb --version');
    const hasEmulator = checkRequirement('emulator', 'emulator -version');

    if (!hasEmulator) {
        log(RED, 'Android Emulator tool is missing.');
        return;
    }

    log(CYAN, '\nScanning for Android Virtual Devices (AVDs)...');
    const avds = runCommand('emulator -list-avds');

    if (avds) {
        const avdList = avds.split('\n');
        log(GREEN, `Found ${avdList.length} AVDs:`);
        avdList.forEach(avd => console.log(` - ${avd}`));

        // Future expansion: Offer to boot one
    } else {
        log(YELLOW, 'No AVDs found.');
        await askToCreateAvd();
    }
}

async function askToCreateAvd() {
    return new Promise((resolve) => {
        rl.question(`\n${YELLOW}Do you want to create a default Pixel emulator (API 35)? (y/n) ${RESET}`, (answer) => {
            if (answer.toLowerCase() === 'y') {
                createAvd();
            }
            resolve();
        });
    });
}

function createAvd() {
    log(CYAN, 'Creating "Pixel_API_35"...');
    // Check for system image first - this is complex to script fully reliably without sdkmanager perfectly set up
    // Simplified attempt:
    try {
        // This assumes system-images;android-35;google_apis;x86_64 is installed.
        // If not, we'd need to run: sdkmanager "system-images;android-35;google_apis;x86_64"
        log(YELLOW, 'Note: This requires the "system-images;android-35;google_apis;x86_64" package to be installed via SDK Manager.');

        execSync('echo "no" | avdmanager create avd -n Pixel_API_35 -k "system-images;android-35;google_apis;x86_64" --force', { stdio: 'inherit' });
        log(GREEN, 'AVD "Pixel_API_35" created successfully!');
    } catch (error) {
        log(RED, 'Failed to create AVD. Make sure you have the system images installed.');
        console.error(error.message);
    }
}

async function setupIos() {
    if (process.platform !== 'darwin') {
        return;
    }

    log(CYAN, '\n=== iOS Setup ===');
    const hasXcrun = checkRequirement('Xcode Tools', 'xcode-select -p');

    if (!hasXcrun) {
        log(RED, 'Xcode tools not found. Please install Xcode.');
        return;
    }

    log(CYAN, '\nScanning for iOS Simulators...');
    try {
        const simOutput = runCommand('xcrun simctl list devices available');
        // Basic parsing to show some devices
        const deviceLines = simOutput.split('\n').filter(line => line.includes('(Booted)') || line.includes('iPhone'));

        if (deviceLines.length > 0) {
            log(GREEN, 'Found available simulators (truncated list):');
            deviceLines.slice(0, 5).forEach(line => console.log(line));
            if (deviceLines.length > 5) console.log(' ...');
        } else {
            log(YELLOW, 'No simulators found. You may need to create one in Xcode.');
        }
    } catch (e) {
        log(RED, 'Error listing simulators.');
    }
}

async function main() {
    log(CYAN, 'Starting Device Setup Assistant...');

    await setupAndroid();
    await setupIos();

    log(CYAN, '\nDone. You can run "npm run android" or "npm run ios" to start the app.');
    rl.close();
}

main();
