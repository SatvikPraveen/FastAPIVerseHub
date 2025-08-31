#!/bin/bash

# File Location: scripts/run_tests.sh
# 
# Comprehensive test runner for FastAPIVerseHub
# Runs different types of tests with proper environment setup

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="all"
COVERAGE=false
VERBOSE=false
PARALLEL=false
EXPORT_RESULTS=false
CLEAN_DB=false

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
FastAPIVerseHub Test Runner

Usage: $0 [OPTIONS]

Options:
    -t, --type TYPE         Test type: unit, integration, e2e, performance, all (default: all)
    -c, --coverage         Run with coverage report
    -v, --verbose          Verbose output
    -p, --parallel         Run tests in parallel
    -e, --export          Export test results
    --clean-db            Clean test database before running
    -h, --help            Show this help message

Examples:
    $0 --type unit --coverage
    $0 --type integration --verbose
    $0 --type all --coverage --export
    $0 --clean-db --parallel

Test Types:
    unit          - Unit tests only
    integration   - Integration tests only  
    e2e          - End-to-end tests
    performance  - Performance/load tests
    all          - All test types (default)
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        -e|--export)
            EXPORT_RESULTS=true
            shift
            ;;
        --clean-db)
            CLEAN_DB=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate test type
case $TEST_TYPE in
    unit|integration|e2e|performance|all)
        ;;
    *)
        print_error "Invalid test type: $TEST_TYPE"
        show_usage
        exit 1
        ;;
esac

print_status "FastAPIVerseHub Test Runner"
print_status "Test type: $TEST_TYPE"
print_status "Coverage: $COVERAGE"
print_status "Verbose: $VERBOSE"
print_status "Parallel: $PARALLEL"

# Check if we're in the correct directory
if [ ! -f "pyproject.toml" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Create test results directory
mkdir -p test-results

# Setup test environment
setup_test_environment() {
    print_status "Setting up test environment..."
    
    # Export test environment variables
    export ENVIRONMENT=testing
    export DATABASE_URL="sqlite:///./test.db"
    export REDIS_URL="redis://localhost:6379/1"
    export SECRET_KEY="test-secret-key-change-in-production"
    export JWT_SECRET_KEY="test-jwt-secret-key"
    
    # Clean test database if requested
    if [ "$CLEAN_DB" = true ]; then
        print_status "Cleaning test database..."
        rm -f test.db test.db-*
    fi
    
    # Check if required services are running
    if ! redis-cli ping > /dev/null 2>&1; then
        print_warning "Redis is not running - some tests may fail"
    fi
}

# Run unit tests
run_unit_tests() {
    print_status "Running unit tests..."
    
    local pytest_args=("app/tests/test_*.py")
    local marks=("-m" "not integration and not e2e and not performance")
    
    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v")
    fi
    
    if [ "$PARALLEL" = true ]; then
        pytest_args+=("-n" "auto")
    fi
    
    if [ "$COVERAGE" = true ]; then
        pytest_args+=("--cov=app" "--cov-report=term-missing" "--cov-report=html:test-results/htmlcov")
    fi
    
    if [ "$EXPORT_RESULTS" = true ]; then
        pytest_args+=("--junit-xml=test-results/unit-tests.xml")
    fi
    
    pytest "${marks[@]}" "${pytest_args[@]}"
}

# Run integration tests
run_integration_tests() {
    print_status "Running integration tests..."
    
    local pytest_args=("app/tests/")
    local marks=("-m" "integration")
    
    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v")
    fi
    
    if [ "$PARALLEL" = true ]; then
        pytest_args+=("-n" "auto")
    fi
    
    if [ "$EXPORT_RESULTS" = true ]; then
        pytest_args+=("--junit-xml=test-results/integration-tests.xml")
    fi
    
    pytest "${marks[@]}" "${pytest_args[@]}"
}

# Run end-to-end tests
run_e2e_tests() {
    print_status "Running end-to-end tests..."
    
    # Check if application is running
    if ! curl -s http://localhost:8000/health > /dev/null; then
        print_warning "Application not running on localhost:8000"
        print_status "Starting application for e2e tests..."
        
        # Start application in background
        uvicorn app.main:app --host 0.0.0.0 --port 8000 &
        APP_PID=$!
        
        # Wait for application to start
        sleep 5
        
        if ! curl -s http://localhost:8000/health > /dev/null; then
            print_error "Failed to start application"
            kill $APP_PID 2>/dev/null || true
            exit 1
        fi
    else
        APP_PID=""
    fi
    
    local pytest_args=("app/tests/")
    local marks=("-m" "e2e")
    
    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v")
    fi
    
    if [ "$EXPORT_RESULTS" = true ]; then
        pytest_args+=("--junit-xml=test-results/e2e-tests.xml")
    fi
    
    pytest "${marks[@]}" "${pytest_args[@]}"
    
    # Clean up application if we started it
    if [ -n "$APP_PID" ]; then
        print_status "Stopping test application..."
        kill $APP_PID 2>/dev/null || true
        wait $APP_PID 2>/dev/null || true
    fi
}

# Run performance tests
run_performance_tests() {
    print_status "Running performance tests..."
    
    # Check if application is running
    if ! curl -s http://localhost:8000/health > /dev/null; then
        print_error "Application must be running for performance tests"
        print_status "Please start the application with: uvicorn app.main:app --host 0.0.0.0 --port 8000"
        exit 1
    fi
    
    # Run benchmark script
    python scripts/benchmark_apis.py --total 50 --concurrent 5 --export test-results/performance-results.json
    
    # Run pytest performance tests if they exist
    local pytest_args=("app/tests/")
    local marks=("-m" "performance")
    
    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v")
    fi
    
    if [ "$EXPORT_RESULTS" = true ]; then
        pytest_args+=("--junit-xml=test-results/performance-tests.xml")
    fi
    
    pytest "${marks[@]}" "${pytest_args[@]}" || true  # Don't fail if no performance tests exist
}

# Run linting and code quality checks
run_quality_checks() {
    print_status "Running code quality checks..."
    
    # Check if linting tools are installed
    if command -v flake8 > /dev/null; then
        print_status "Running flake8..."
        flake8 app/ --max-line-length=88 --extend-ignore=E203,W503 || print_warning "Flake8 warnings found"
    fi
    
    if command -v black > /dev/null; then
        print_status "Checking code formatting with black..."
        black --check app/ || print_warning "Code formatting issues found"
    fi
    
    if command -v mypy > /dev/null; then
        print_status "Running type checks with mypy..."
        mypy app/ || print_warning "Type checking issues found"
    fi
}

# Generate test report
generate_test_report() {
    if [ "$EXPORT_RESULTS" = true ]; then
        print_status "Generating test report..."
        
        cat > test-results/README.md << EOF
# Test Results

Generated on: $(date)

## Test Files

- \`unit-tests.xml\` - Unit test results (JUnit format)
- \`integration-tests.xml\` - Integration test results (JUnit format)  
- \`e2e-tests.xml\` - End-to-end test results (JUnit format)
- \`performance-tests.xml\` - Performance test results (JUnit format)
- \`performance-results.json\` - Detailed performance benchmark results
- \`htmlcov/\` - HTML coverage report (if coverage was enabled)

## How to View Results

### Coverage Report
Open \`htmlcov/index.html\` in your browser to view the detailed coverage report.

### Performance Results
The \`performance-results.json\` file contains detailed performance metrics including:
- Response times (average, min, max, p95)
- Requests per second
- Error rates
- Individual endpoint performance

### JUnit XML Files
These can be imported into CI/CD systems or test result viewers for detailed analysis.
EOF
        
        print_success "Test report generated in test-results/"
    fi
}

# Main execution
main() {
    setup_test_environment
    
    case $TEST_TYPE in
        unit)
            run_unit_tests
            ;;
        integration)  
            run_integration_tests
            ;;
        e2e)
            run_e2e_tests
            ;;
        performance)
            run_performance_tests
            ;;
        all)
            print_status "Running all test types..."
            
            # Always run quality checks first
            run_quality_checks
            
            # Run unit tests (fastest)
            run_unit_tests
            
            # Run integration tests
            run_integration_tests
            
            # Run e2e tests (slowest)
            run_e2e_tests
            
            # Run performance tests last
            print_status "Performance tests require the application to be running"
            if curl -s http://localhost:8000/health > /dev/null; then
                run_performance_tests
            else
                print_warning "Skipping performance tests - application not running"
            fi
            ;;
    esac
    
    generate_test_report
    print_success "Test execution completed!"
}

# Install required packages if missing
install_dependencies() {
    if ! command -v pytest > /dev/null; then
        print_status "Installing pytest..."
        pip install pytest pytest-asyncio pytest-cov
    fi
    
    if [ "$PARALLEL" = true ] && ! pip show pytest-xdist > /dev/null 2>&1; then
        print_status "Installing pytest-xdist for parallel execution..."
        pip install pytest-xdist
    fi
}

# Check dependencies and run main
install_dependencies
main

exit $?