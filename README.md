# Analyze This

## Description

Analyze This is a tool to review media shared through web or mobile interface through the "share this" feature. The tool will analyze the media looking for dates, locations, and principals.

In the default case, provided a date and time are provided, the tool will update the ical feed it serves with the new event. When information is missing, the tool will create a follow up for human media enrichment.

## Setup

### Mobile App

The mobile application is located in the `mobile/` directory and uses React Native (Expo).

1.  **Navigate to directory**: `cd mobile`
2.  **Install dependencies**: `npm install`
3.  **Run on iOS**: `npx expo run:ios` (Requires Xcode)
4.  **Run on Android**: `npx expo run:android` (Requires Android Studio)

**Important**: Testing the "Share" intent requires a Development Build (`npx expo run:ios/android`). It will not work in standard Expo Go.

For detailed verification steps, see the [Walkthrough](file:///Users/bwilson/.gemini/antigravity/brain/5d3c40ca-2baf-4861-95a6-d24494436b93/walkthrough.md).
