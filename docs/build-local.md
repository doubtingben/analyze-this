# Build Local

There's a prompt at prompts/build-local.md that can be used to deploy a backend branch and build the mobile apps for manual upload to the Play Store and TestFlight.


Use like this:
```
gemini --yolo --debug -p "$(cat prompts/build-local.md)"
```

Append additional context to the prompt like this:
```
gemini --yolo --debug -p "$(cat prompts/build-local.md) use branch feature/timeline-followup-views"
```

