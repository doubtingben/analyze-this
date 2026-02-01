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
worker-deploy: ## Deploy worker to Google Cloud Run (Service)
	./backend/scripts/deploy-worker.sh

# ================================
# Flutter
# ================================

.PHONY: flutter-install
flutter-install: ## Install Flutter dependencies
	cd flutter && flutter pub get

.PHONY: flutter-clean
flutter-clean: ## Clean Flutter build
	cd flutter && flutter clean

.PHONY: flutter-run
flutter-run: ## Run Flutter app
	cd flutter && flutter run

.PHONY: flutter-run-android
flutter-run-android: ## Run Flutter app on Android
	cd flutter && flutter run -d android

.PHONY: flutter-run-ios
flutter-run-ios: ## Run Flutter app on iOS
	cd flutter && flutter run -d ios

.PHONY: flutter-build-apk
flutter-build-apk: ## Build Android APK (Release)
	cd flutter && flutter build apk --release

.PHONY: flutter-build-appbundle
flutter-build-appbundle: ## Build Android App Bundle (Release)
	cd flutter && flutter build appbundle --release

.PHONY: flutter-build-ios
flutter-build-ios: ## Build iOS app .app (Release, no codesign)
	cd flutter && flutter build ios --release --no-codesign

.PHONY: flutter-build-ipa
flutter-build-ipa: ## Build iOS app .ipa (Release, requires signing)
	cd flutter && flutter build ipa --release

.PHONY: flutter-test
flutter-test: ## Run Flutter tests
	cd flutter && flutter test

.PHONY: flutter-lint
flutter-lint: ## Run Flutter analyzer
	cd flutter && flutter analyze

.PHONY: flutter-format
flutter-format: ## Format Flutter code
	cd flutter && dart format .

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
verify: backend-check flutter-build-apk ## Run full verification (backend + mobile builds)

.PHONY: ci
ci: test verify ## Run CI pipeline locally

# ================================
# Setup
# ================================

.PHONY: install
install: backend-install flutter-install ## Install all dependencies

.PHONY: clean
clean: ## Clean all builds
	rm -rf backend/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	cd flutter && flutter clean

# ================================
# Default
# ================================

.DEFAULT_GOAL := help
