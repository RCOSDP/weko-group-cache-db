#!/bin/bash

install_deps() {
    # Install Python dependencies
    pip install --upgrade pip && pip install uv
    uv sync && uv pip install -e .

    if ! grep -q "venv_activate_reload" ~/.bashrc 2>/dev/null; then
        {
        echo ""
        echo "# venv_activate_reload"
        echo "if [ -f ~/.venv/bin/activate ]; then"
        echo "  source ~/.venv/bin/activate"
        echo "fi"
        } >> ~/.bashrc
    fi
}


compose_up() {
    docker compose up -d --force-recreate redis
}

FUNCTION_NAME=$1

if [ -z "$FUNCTION_NAME" ]; then
    echo "Error: Function name argument is missing."
    exit 1
fi

shift

if type -t "$FUNCTION_NAME" | grep -q 'function'; then
    "$FUNCTION_NAME" "$@"
else
    echo "Error: Function '$FUNCTION_NAME' not found."
    exit 1
fi
