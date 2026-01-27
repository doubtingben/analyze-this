# Analyze This - Project Makefile
# ================================

.PHONY: help
help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ================================
# Backend
# ================================

.PHONY: backend-install
backend-install: ## Install backend dependencies
	cd backend && pip install -r requirements.txt

.PHONY: backend-run
backend-run: ## Run the backend server locally
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

.PHONY: backend-test
backend-test: ## Run backend tests
	python -m unittest backend/tests/test_analysis.py

.PHONY: backend-check
backend-check: ## Verify backend starts correctly
	./backend/scripts/check-backend-start.sh

.PHONY: backend-docker-build
backend-docker-build: ## Build backend Docker image
	docker build -t analyze-this-backend .

.PHONY: backend-docker-run
backend-docker-run: ## Run backend Docker container locally
	docker run -p 8000:8080 -e PORT=8080 analyze-this-backend

.PHONY: backend-deploy
backend-deploy: ## Deploy backend to Google Cloud Run
	./backend/scripts/deploy.sh

.PHONY: worker-deploy
worker-deploy: ## Deploy worker to Google Cloud Run Jobs
	./backend/scripts/deploy-worker.sh

# ================================
# Mobile - General
# ================================

.PHONY: mobile-install
mobile-install: ## Install mobile dependencies
	cd mobile && npm install

.PHONY: mobile-start
mobile-start: ## Start Expo development server
	cd mobile && npm start

.PHONY: mobile-lint
mobile-lint: ## Run mobile linting
	cd mobile && npm run lint

.PHONY: mobile-build
mobile-build: ## Build mobile app for both platforms
	./mobile/scripts/build-mobile.sh

.PHONY: mobile-eas-build
mobile-eas-build: ## Build mobile app with EAS (Preview)
	cd mobile && npx eas-cli build --platform all --profile preview --non-interactive

.PHONY: mobile-eas-build-ios
mobile-eas-build-ios: ## Build iOS app with EAS (Preview)
	cd mobile && npx eas-cli build --platform ios --profile preview --non-interactive

.PHONY: mobile-eas-submit-ios
mobile-eas-submit-ios: ## Submit latest iOS build to TestFlight
	cd mobile && npx eas-cli submit --platform ios --profile preview --latest

.PHONY: mobile-eas-build-submit-ios
mobile-eas-build-submit-ios: ## Build iOS and auto-submit to TestFlight
	cd mobile && npx eas-cli build --platform ios --profile preview --auto-submit --non-interactive

.PHONY: mobile-setup-devices
mobile-setup-devices: ## Setup Android/iOS devices and emulators
	cd mobile && npm run setup-devices

.PHONY: mobile-reset
mobile-reset: ## Reset mobile project to blank state
	cd mobile && npm run reset-project

# ================================
# Mobile - Android
# ================================

.PHONY: android-run
android-run: ## Build and run Android app
	cd mobile && npm run android

.PHONY: android-build
android-build: ## Build Android release APK
	cd mobile/android && ./gradlew assembleRelease

.PHONY: android-build-debug
android-build-debug: ## Build Android debug APK
	cd mobile/android && ./gradlew assembleDebug

.PHONY: android-clean
android-clean: ## Clean Android build
	cd mobile/android && ./gradlew clean

# ================================
# Mobile - iOS
# ================================

.PHONY: ios-run
ios-run: ## Build and run iOS app
	cd mobile && npm run ios

.PHONY: ios-build
ios-build: ## Build iOS app (requires macOS)
	cd mobile/ios && xcodebuild -workspace AnalyzeThis.xcworkspace -scheme AnalyzeThis -configuration Release -sdk iphoneos

.PHONY: ios-build-simulator
ios-build-simulator: ## Build iOS app for simulator
	cd mobile/ios && xcodebuild -workspace AnalyzeThis.xcworkspace -scheme AnalyzeThis -configuration Debug -sdk iphonesimulator

.PHONY: ios-clean
ios-clean: ## Clean iOS build
	cd mobile/ios && xcodebuild clean

.PHONY: ios-pod-install
ios-pod-install: ## Install iOS CocoaPods dependencies
	cd mobile/ios && pod install

# ================================
# Mobile - Web
# ================================

.PHONY: web-run
web-run: ## Start web version
	cd mobile && npm run web

# ================================
# Mobile - Flutter
# ================================

.PHONY: flutter-install
flutter-install: ## Install Flutter dependencies
	cd analyze_this_flutter && flutter pub get

.PHONY: flutter-clean
flutter-clean: ## Clean Flutter build
	cd analyze_this_flutter && flutter clean

.PHONY: flutter-run
flutter-run: ## Run Flutter app
	cd analyze_this_flutter && flutter run

.PHONY: flutter-run-android
flutter-run-android: ## Run Flutter app on Android
	cd analyze_this_flutter && flutter run -d android

.PHONY: flutter-run-ios
flutter-run-ios: ## Run Flutter app on iOS
	cd analyze_this_flutter && flutter run -d ios

.PHONY: flutter-build-apk
flutter-build-apk: ## Build Android APK (Release)
	cd analyze_this_flutter && flutter build apk --release

.PHONY: flutter-build-appbundle
flutter-build-appbundle: ## Build Android App Bundle (Release)
	cd analyze_this_flutter && flutter build appbundle --release

.PHONY: flutter-build-ios
flutter-build-ios: ## Build iOS app .app (Release, no codesign)
	cd analyze_this_flutter && flutter build ios --release --no-codesign

.PHONY: flutter-build-ipa
flutter-build-ipa: ## Build iOS app .ipa (Release, requires signing)
	cd analyze_this_flutter && flutter build ipa --release

.PHONY: flutter-test
flutter-test: ## Run Flutter tests
	cd analyze_this_flutter && flutter test

.PHONY: flutter-lint
flutter-lint: ## Run Flutter analyzer
	cd analyze_this_flutter && flutter analyze

.PHONY: flutter-format
flutter-format: ## Format Flutter code
	cd analyze_this_flutter && dart format .

# ================================
# Worker Analysis
# ================================

.PHONY: worker-analyze
worker-analyze: ## Analyze N unanalyzed items (N=10, FORCE=0)
	cd backend && python worker_analysis.py --limit $(or $(N),10) $(if $(filter 1,$(FORCE)),--force,)

.PHONY: worker-analyze-id
worker-analyze-id: ## Analyze specific item by ID (ID=xxx required, FORCE=0)
ifndef ID
	$(error ID is required. Usage: make worker-analyze-id ID=your-item-id [FORCE=1])
endif
	cd backend && python worker_analysis.py --id $(ID) $(if $(filter 1,$(FORCE)),--force,)

# ================================
# CI / Testing
# ================================

.PHONY: test
test: backend-test ## Run all tests

.PHONY: verify
verify: backend-check mobile-build ## Run full verification (backend + mobile builds)

.PHONY: ci
ci: test verify ## Run CI pipeline locally

# ================================
# Setup
# ================================

.PHONY: install
install: backend-install mobile-install ## Install all dependencies

.PHONY: clean
clean: android-clean ## Clean all builds
	rm -rf mobile/node_modules
	rm -rf backend/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ================================
# Default
# ================================

.DEFAULT_GOAL := help
