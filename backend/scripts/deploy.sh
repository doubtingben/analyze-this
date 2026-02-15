#!/usr/bin/env bash
set -e

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Help function
show_help() {
    echo "Usage: ./deploy.sh [OPTIONS]"
    echo "Deploys backend services. If no options are provided, deploys ALL services."
    echo ""
    echo "Options:"
    echo "  --backend       Deploy the main backend API"
    echo "  --workers       Deploy worker Cloud Run Jobs (analysis, normalize, follow_up)"
    echo "  --manager       Deploy the manager service"
    echo "  --all           Deploy all services (default)"
    echo "  --help          Show this help message"
}

# State variables
DEPLOY_BACKEND=false
DEPLOY_WORKERS=false
DEPLOY_MANAGER=false

# Check args
if [ $# -eq 0 ]; then
    DEPLOY_BACKEND=true
    DEPLOY_WORKERS=true
    DEPLOY_MANAGER=true
else
    for arg in "$@"; do
        case $arg in
            --backend)
                DEPLOY_BACKEND=true
                ;;
            --workers)
                DEPLOY_WORKERS=true
                ;;
            --manager)
                DEPLOY_MANAGER=true
                ;;
            --all)
                DEPLOY_BACKEND=true
                DEPLOY_WORKERS=true
                DEPLOY_MANAGER=true
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown argument: $arg"
                show_help
                exit 1
                ;;
        esac
    done
fi

# Execute deployments
if [ "$DEPLOY_BACKEND" = true ]; then
    echo "========================================"
    echo "Deploying Backend API..."
    echo "========================================"
    "$SCRIPT_DIR/deploy-backend.sh"
    echo ""
fi

if [ "$DEPLOY_WORKERS" = true ]; then
    echo "========================================"
    echo "Deploying Worker Cloud Run Jobs..."
    echo "========================================"
    "$SCRIPT_DIR/deploy-worker-job.sh" all
    echo ""
fi

if [ "$DEPLOY_MANAGER" = true ]; then
    echo "========================================"
    echo "Deploying Manager Service..."
    echo "========================================"
    "$SCRIPT_DIR/deploy-worker.sh" manager
    echo ""
fi

echo "All requested deployments completed."
