#!/bin/bash
# Local build script — works in environments where Maven Central is
# blocked or unavailable. Uses javac directly with apt-installed JARs.
#
# Normal users with internet access should use Maven: `mvn clean test`.
#
# Usage:
#   ./build.sh build    # compile all modules
#   ./build.sh test     # compile + run all tests
#   ./build.sh clean    # remove build artifacts

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD="$ROOT/build"
CLASSES="$BUILD/classes"
TEST_CLASSES="$BUILD/test-classes"

# JARs from apt (libgoogle-gson-java, junit4, libhamcrest-java)
GSON_JAR="/usr/share/java/gson.jar"
JUNIT_JAR="/usr/share/java/junit4.jar"
HAMCREST_JAR="/usr/share/java/hamcrest.jar"

MODULES=(
    iaiso-audit
    iaiso-core
    iaiso-consent
    iaiso-policy
    iaiso-coordination
    iaiso-middleware
    iaiso-identity
    iaiso-metrics
    iaiso-observability
    iaiso-conformance
    iaiso-cli
)

clean() {
    rm -rf "$BUILD"
    echo "cleaned"
}

# Build classpath for compilation. Modules compile in dependency order.
# Each module's compiled classes are added to the classpath for later
# modules. We use a single output directory so cross-module references
# Just Work.
build() {
    mkdir -p "$CLASSES"
    local cp="$GSON_JAR:$CLASSES"
    for m in "${MODULES[@]}"; do
        local src_dir="$ROOT/$m/src/main/java"
        if [ ! -d "$src_dir" ]; then
            continue
        fi
        local sources
        sources=$(find "$src_dir" -name '*.java' 2>/dev/null || true)
        if [ -z "$sources" ]; then
            continue
        fi
        echo "compile: $m"
        # shellcheck disable=SC2086
        javac --release 17 -d "$CLASSES" -cp "$cp" $sources
    done
    echo "build complete"
}

# Compile + run tests.
test_all() {
    build
    mkdir -p "$TEST_CLASSES"
    local main_cp="$GSON_JAR:$CLASSES"
    local test_cp="$main_cp:$JUNIT_JAR:$HAMCREST_JAR:$TEST_CLASSES"
    local total=0
    for m in "${MODULES[@]}"; do
        local test_src="$ROOT/$m/src/test/java"
        if [ ! -d "$test_src" ]; then
            continue
        fi
        local sources
        sources=$(find "$test_src" -name '*.java' 2>/dev/null || true)
        if [ -z "$sources" ]; then
            continue
        fi
        echo "compile-tests: $m"
        # shellcheck disable=SC2086
        javac --release 17 -d "$TEST_CLASSES" -cp "$test_cp" $sources
    done

    # Discover test classes and run them
    local test_classes=()
    while IFS= read -r f; do
        # Convert path to fully-qualified class name
        local rel="${f#$TEST_CLASSES/}"
        local fqcn="${rel%.class}"
        fqcn="${fqcn//\//.}"
        # Skip inner classes
        case "$fqcn" in
            *\$*) continue ;;
        esac
        # Only run classes whose name ends in Test
        case "$fqcn" in
            *Test|*Tests) test_classes+=("$fqcn") ;;
        esac
    done < <(find "$TEST_CLASSES" -name '*.class' 2>/dev/null | sort)

    if [ ${#test_classes[@]} -eq 0 ]; then
        echo "no tests found"
        return 0
    fi

    echo "running ${#test_classes[@]} test class(es)..."
    java -cp "$test_cp" org.junit.runner.JUnitCore "${test_classes[@]}"
}

case "${1:-build}" in
    build) build ;;
    test) test_all ;;
    clean) clean ;;
    *) echo "usage: $0 [build|test|clean]"; exit 1 ;;
esac
