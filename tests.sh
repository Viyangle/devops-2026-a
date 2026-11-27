set -eu

check() {
    expected=$1
    shift
    actual=$(./app "$@")
    if [ "$actual" != "$expected" ]; then
        printf 'app %s: expected %s, got %s\n' "$*" "$expected" "$actual" >&2
        exit 1
    fi
}

check 1
check 1 7 4
check 0 8 4
check 1 0 1
check 0 12 7
check 1 13 8
check 0 14 8

if ./app -1 0 > /dev/null 2>&1; then
    printf 'app accepted a negative quantity\n' >&2
    exit 1
fi
