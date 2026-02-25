# Development Guide

This guide explains how to set up the development environment for the Voltx Modbus integration using a Dev Container.

## Prerequisites

- [Docker](https://www.docker.com/get-started) installed and running
- [Visual Studio Code](https://code.visualstudio.com/)
- [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) for VS Code

## Getting Started

### 1. Open the Project in Dev Container

1. Open this project folder in Visual Studio Code
2. When prompted, click **"Reopen in Container"** (or press `F1` and select **"Dev Containers: Reopen in Container"**)
3. Wait for the container to build and start — this may take a few minutes on first run

The dev container runs `ghcr.io/home-assistant/devcontainer:addons`, which is a full supervised Home Assistant instance running inside Docker-in-Docker.

### 2. Start Home Assistant

Once the dev container is running:

1. Press `Ctrl+Shift+B` / `Cmd+Shift+B` to run the default build task, **or**
2. Open the Command Palette (`F1`) → **"Tasks: Run Task"** → **"Start Home Assistant"**

### 3. Access Home Assistant

Once Home Assistant starts it will be available at:

http://localhost:7123

The initial startup may take a minute or two. You can monitor progress in the VS Code terminal.

Complete the normal Home Assistant onboarding (create an account, etc.) on first run.

### 4. Add the Integration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **"Voltx Modbus"**
3. Enter the **host IP**, **port** (default 502) and **slave ID** (default 3) for your inverter
4. Click **Submit**

## Development Workflow

Your `custom_components/voltx_modbus/` directory is bind-mounted directly into the container at `/mnt/supervisor/homeassistant/custom_components/`. This means:

- **Edits are live** — no file copying needed
- To pick up code changes, either:
  - Reload the integration via **Settings → Devices & Services → Voltx Modbus → ⋮ → Reload**, or
  - Restart Home Assistant by stopping and re-running the **"Start Home Assistant"** task

## Troubleshooting

- **Home Assistant fails to start:** check the VS Code terminal output for error messages
- **Integration not found:** confirm `custom_components/voltx_modbus/` exists and contains `manifest.json`
- **Cannot connect to inverter:** verify the host IP, port (502) and slave ID are correct; check the inverter is reachable from your host machine
- **Container issues:** rebuild via `F1` → **"Dev Containers: Rebuild Container"**

## Port Mapping

| Host port | Container port | Service           |
| --------- | -------------- | ----------------- |
| 7123      | 8123           | Home Assistant UI |
| 7357      | 4357           | HA debugger       |
