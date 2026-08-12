# NekoFlow: Graphical Client for Network Tunneling Based on the APTCP Session Protocol

> **Translation Note:** This document is an English translation of the original Russian README. While care was taken to maintain consistency, it may contain minor translation inaccuracies or slight terminology differences from the original Russian text. The Russian version remains the primary reference.

> ### Important Notice (Disclaimer)
> The NekoFlow software is developed solely as a tool to improve the stability, resilience, and security of network connections (specifically, to prevent session drops on unstable physical communication channels).
>
> The project developers do not provide ready-made servers or traffic routing services. Any actions related to deploying the server-side component on third-party resources, configuring routes, and using the program for other purposes are carried out by users independently and under their own responsibility. The developers are not liable for any potential violations of local legislation resulting from the use of this software.

---

**NekoFlow** is a specialized desktop application for Windows, representing a graphical user interface (GUI) over the client part of the **APTCP-SOCKS** network solution. The program provides traffic routing and local proxying via the fault-tolerant APTCP transport protocol (utilizing the `aioptcp` library), operating on top of the standard TCP stack.

The project is delivered as a **Portable** package: the archive contains the compiled native C# launcher `NekoFlow.exe`, an embedded portable Python 3.12 interpreter, required system binaries (the `sing-box` core and the `Wintun` driver), and the PySide6-based graphical interface.

---

## Network Transport Architecture (APTCP & aioptcp)

At the core of the client lies the **APTCP** session-layer protocol, designed to ensure high fault tolerance for network connections during unstable network conditions, interface handovers (e.g., Wi-Fi to LTE), or IP address changes.

### Key Features of the Transport:
1. **Logical Connection Resilience:** When the physical TCP link is lost, the logical APTCP connection does not drop; instead, it transitions to the `DISCONNECTED_WAITING` state. Data transmitted by the application is buffered, and system calls to `send()` and `recv()` temporarily block. Once the physical channel is restored, the session resumes automatically without any packet loss or disconnection of user TCP sockets.
2. **Backpressure / Flow Control:** Limiting the transmission buffer volume (by default, up to 5 MB) prevents uncontrolled RAM allocation during prolonged network outages.
3. **Secure Session Resumption:** Reconnection is secured via a mutual 3-way Challenge-Response handshake using HMAC-SHA256 signatures derived from a shared secret generated during the initial Diffie-Hellman exchange (2048-bit MODP Group). This protects the protocol against session hijacking (MitM) and replay attacks.
4. **Secure Session Closure:** The connection teardown command (`CLOSE`) is signed with a unique HMAC-SHA256 signature bound to the current session, protecting against unauthorized third-party injection of connection termination packets.

---

## Client Operation Modes

The application supports two primary scenarios for operating system integration:

### 1. TUN Mode (Network Tunnel)
Traffic is intercepted at the network layer using the virtual adapter named `NekoFlow` (utilizing the `Wintun` driver) managed by the `sing-box` router (located in `bin/sing-box.exe`).
* **Split Tunneling:** Routing is configured so that only traffic from specified applications added to the whitelist (e.g., `chrome.exe`, `discord.exe`) is directed through the tunnel. Traffic from all other programs flows directly through the physical network adapter, reducing the load on the remote server.
* **Global Tunnel:** All system traffic (except for local networks and service processes) is directed into the secure channel.

### 2. SOCKS Proxy (Local Proxy Server)
The client starts an isolated local SOCKS5 server on port `3080`.
* The routing scheme does not modify the global Windows routing table, avoiding conflicts with other virtual network interfaces.
* Traffic from required applications is directed to the local address `127.0.0.1:3080` manually or using external capturing utilities (such as Proxifier or Postern).

---

## Authorization and Transport Protection

The system segregates access at the local operating system level and the network transport level:

1. **Local Access (Application/Proxifier → Local SOCKS Server)**
   * At the NekoFlow GUI level, the local SOCKS server on port `3080` always operates **without authentication** (anonymous access). External redirector programs (such as Proxifier) must connect to it without specifying credentials.
   * If you require strict access control on the local port, you can use specialized low-level system utilities or modify the client-side SOCKS server code in the `client/socks_server.py` file yourself.

2. **Transport Authorization (Local Client → Remote APTCP Server)**
   * For authorization on your remote server, credentials are configured directly in the NekoFlow graphical interface in the **"Server Management"** menu.
   * The username and password set in the GUI must exactly match those specified during server deployment (saved in `users.jsonl` on the server).
   * The transport handshake procedure is performed automatically by the client in the background. Client applications (such as Proxifier) are not involved in this process.

3. **TLS Encryption and Certificate Management**
   * If encryption was activated during your server setup, you will need to transfer the public `.pem` certificate file to the client computer.
   * It is recommended to create a folder named `tls` in the root directory of this application (if it does not exist) and place the certificate file there. Then, specify the relative path to the certificate in the server settings within the program interface.

---

## Important Stability and Troubleshooting Guidelines

* **Verify Connection Before Launching:** Before turning on the main connection toggle, it is highly recommended to open the **"Server Management"** menu, select the current server, and click the **"Test"** button. The program will execute a test isolated handshake with the server and verify the correctness of the login, password, and transport channel availability.
* **TUN Interface Initialization:** Due to the Wintun driver characteristics in Windows, the virtual adapter `NekoFlow` may sometimes fail to create or mount on the first attempt. If you encounter an interface initialization error when attempting to connect in TUN mode, it is recommended to **completely restart the program** as Administrator and try to connect again.

---

## Project Directory Tree

```text
├── .idea/                  # PyCharm IDE configuration files
├── .pytest_cache/          # pytest framework temporary cache
├── .venv/                  # Local virtual environment for development and testing
├── bin/                    # Binary routing engine utilities
│   ├── sing-box.exe        # sing-box executable for packet capturing in TUN mode
│   └── wintun.dll          # Wintun virtual network adapter driver
├── client/                 # Local proxy client logic
│   ├── aptcp_client.py     # Initiates APTCP sessions and handles transport handshake
│   ├── direct_socks_server.py # Fallback SOCKS5 server without APTCP encapsulation (for testing)
│   ├── main.py             # Entry point for the CLI client
│   ├── socks_server.py     # Local async SOCKS5 server (handles TCP CONNECT, UDP ASSOCIATE)
│   └── users.jsonl         # Local authentication registry for client applications
├── common/                 # Shared network and configuration libraries
│   ├── config.py           # JSON/JSONL configuration validator
│   ├── socks5.py           # Low-level parser for SOCKS5 protocol structures (RFC 1928 / RFC 1929)
│   └── tunnel.py           # PTCPStream class, UDP framing, and session commands processing
├── images/                 # GUI visual assets and icons
├── python/                 # Portable built-in Python 3.12 interpreter
│   ├── python312.dll       # Python interpreter core dynamic link library
│   └── ...                 # Standard modules and compiled libraries
├── src/                    # NekoFlow GUI source code
│   ├── network/            # Process routing and routing table controllers
│   │   ├── base_engine.py  # Abstract base class for network engines
│   │   ├── process_finder.py# Retrieves PID and process name by local port (Win32 API)
│   │   ├── route_manager.py# Windows routing table backup and recovery module
│   │   ├── socks_engine.py # Wrapper for launching the local SOCKS proxy
│   │   └── tun_engine.py   # sing-box core orchestrator for TUN mode
│   ├── ui/                 # Qt-based UI components (PySide6)
│   │   ├── custom_title_bar.py # Custom title bar widget for frameless windows
│   │   ├── main_window.py  # Main window manager (thread lifecycle, tray menu, toggles)
│   │   ├── process_dialog.py # Whiteliest configuration dialog for split tunneling
│   │   ├── server_dialog.py# Server manager configuration dialog (TLS, connection tester)
│   │   ├── style.py        # Stylesheet definitions (Dark Graphite & Crimson Red)
│   │   └── toggle_switch.py# Animated switch widget for initiating connection
│   └── utils/              # OS integration utilities
│       └── admin.py        # Windows administrator privileges helper
├── tests/                  # Autotests suite (Unit, Integration, E2E)
├── connecter_config.json   # Local GUI configurations and servers storage
├── Launcher.cs             # C# source code for the native launcher bootstrapper
├── LICENSE                 # GPLv3 License text
├── main.py                 # Main entry point for python-driven GUI startup
├── NekoFlow.exe            # Compiled native Windows launcher executable
├── NekoFlow.manifest       # Manifest file for automatic UAC administrator prompt
├── pytest.ini              # pytest framework configuration
├── requirements.txt        # GUI python dependencies checklist
└── singbox.log             # Technical log file for the sing-box core
```

---

## Native Launcher (NekoFlow.exe)

End users execute the graphical interface through the `NekoFlow.exe` binary. This represents a compiled C# loader based on `Launcher.cs` that operates as follows:
1. It shifts the application's current working directory to the directory where the executable file is located.
2. It uses the `SetDllDirectory` WinAPI function to set the `python/` folder as the priority directory for finding dynamic link libraries.
3. It loads the `python312.dll` interpreter using the `LoadLibrary` system call.
4. It resolves the address of the `Py_Main` entry point in the DLL and invokes it, passing the path to the main script `main.py` as an argument.
5. Thanks to the embedded `NekoFlow.manifest` file, the process guarantees a UAC Administrator prompt on startup, which is critical for mounting the virtual `Wintun` adapter and modifying the Windows routing tables.

---

## Server Setup & Deployment (Linux)

To use the client, you must deploy the corresponding server handler on a remote Linux server (VPS).

The server source code and deployment environment are located in the repository: [APTCP-SOCKS](https://github.com/Doctorgth/APTCP-SOCKS)

### Quick Server Installation (Docker Container):
To automatically build the server and configure TLS encryption, execute the following one-line command on your remote machine:
```bash
curl -O https://raw.githubusercontent.com/Doctorgth/APTCP-SOCKS/main/install.sh && sed -i 's/\r//' install.sh && chmod +x install.sh && ./install.sh
```
During installation, the script will:
* Prompt for the desired communication port, username, and password.
* Generate self-signed TLS certificates for transport encryption (`server/cert.pem`, `server/key.pem`).
* Display connection details in the console and output the command to start the service in the background.

*Note: Docker and Docker Compose must be pre-installed on the server for the automated container script to run.*

---

## TLS Encryption Setup

If needed, the APTCP protocol supports standard Transport Layer Security (TLS) encryption to ensure data confidentiality and remote node authentication.

1. **Preparing the Certificate:** If encryption was activated during server setup, copy the public certificate file `cert.pem` from the server to your local machine. It is recommended to save it inside a folder named `tls` in the application's root directory.
2. **Client Configuration:** In the NekoFlow GUI, open the **"Server Management"** menu, select the desired server entry, tick the **"Use TLS"** checkbox, click the file selection button `...`, and specify the path to your `.pem` file.
3. **Verification:** Utilizing a TLS certificate ensures that the network channel is protected from unauthorized tampering and confirms that the client has established a connection specifically with your verified server.

---

## Development and Testing Run

Developers can run the project source code directly without compiling or using the native launcher.

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch App from Terminal
```bash
python main.py
```

### 3. Run Autotests
To verify network engines, packet parsers, encryption, and logging components, run `pytest` from the root directory:
```bash
pytest -v
```

---

## License

This project is distributed under the terms of the **GNU General Public License v3 (GPLv3)**. Detailed terms and conditions for copying and distributing the source code are available in the `LICENSE` file.

The distribution includes the following third-party components under their respective licenses:
* **Sing-box** (GPLv3) — https://github.com/SagerNet/sing-box
* **Wintun** (GPLv2) — https://www.wintun.net/
* **Python** (PSFL) — https://docs.python.org/3/license.html
* **PySide6 / Qt** (LGPLv3) — https://doc.qt.io/qtforpython-6/