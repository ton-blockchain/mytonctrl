# Interactive Docker Bash shortcuts. Read configuration when invoked so port
# changes and migrated installations use the active local node.
_mytonctrl_work_dir() {
    if [[ -r /run/mytonctrl-options.json ]]; then
        jq -er '.TON_WORK_DIR | select(type == "string" and startswith("/"))' /run/mytonctrl-options.json
    else
        printf '%s\n' "${TON_WORK_DIR:-/var/ton-work}"
    fi
}

_mytonctrl_node_port() {
    jq -er --arg endpoint "$2" '
        .[$endpoint] |
        if type == "array" and length == 1 then .[0].port
        else error("expected one " + $endpoint + " endpoint") end |
        if type == "number" then
            if . >= 1 and . <= 65535 and floor == . then .
            else error("invalid " + $endpoint + " port") end
        else error("missing " + $endpoint + " port") end
    ' "$1/db/config.json"
}

_mytonctrl_lite_client() {
    local work port
    work=$(_mytonctrl_work_dir) || return
    port=$(_mytonctrl_node_port "$work" liteservers) || return
    /run/ton-active/bin/lite-client -p "$work/keys/liteserver.pub" \
        -a "127.0.0.1:$port" -t 3 "$@"
}

_mytonctrl_validator_console() {
    local work port
    work=$(_mytonctrl_work_dir) || return
    port=$(_mytonctrl_node_port "$work" control) || return
    /run/ton-active/bin/validator-engine-console -k "$work/keys/client" \
        -p "$work/keys/server.pub" -a "127.0.0.1:$port" "$@"
}

_mytonctrl_sync() {
    local output status
    if output=$(_mytonctrl_lite_client -c last 2>&1); then
        printf '%s\n' "$output" |
            sed -nE 's/.*\(([0-9]+([.][0-9]+)?) seconds? ago\).*/\1/p' | tail -n1
    else
        status=$?
        printf '%s\n' "$output" >&2
        return "$status"
    fi
}

alias config32='_mytonctrl_lite_client -c "getconfig 32"'
alias config34='_mytonctrl_lite_client -c "getconfig 34"'
alias config36='_mytonctrl_lite_client -c "getconfig 36"'
alias elid='_mytonctrl_lite_client -c "runmethod -1:3333333333333333333333333333333333333333333333333333333333333333 active_election_id"'
alias getstats='_mytonctrl_validator_console -c getstats'
alias last='_mytonctrl_lite_client -c last'
alias participants='_mytonctrl_lite_client -c "runmethod -1:3333333333333333333333333333333333333333333333333333333333333333 participant_list"'
alias sync='_mytonctrl_sync'
