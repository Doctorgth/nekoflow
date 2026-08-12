# NekoFlow: User Manual
# NekoFlow: Graphical Client for Network Tunneling Based on the APTCP Session Protocol

> **Translation Note:** This document is an English translation of the original Russian README. While care was taken to maintain consistency, it may contain minor translation inaccuracies or slight terminology differences from the original Russian text. The Russian version remains the primary reference.

> ### ⚠️ Important Notice (Disclaimer)
> The NekoFlow software is developed solely as an auxiliary tool to improve the stability, resilience, and security of network connections. This tool **is not intended** for bypassing blocks, access restrictions, or any other forms of network censorship.
> 
> The project developers do not provide ready-made servers or traffic routing services. Any actions related to deploying the server-side component on third-party resources and using the program are carried out by users under their own personal responsibility.

---

## What is APTCP and Why Do You Need Seamless Reconnect?

When using a standard internet connection, any temporary network disruption (dropping Wi-Fi signal, switching to a mobile LTE network, or momentary packet loss on the ISP's side) causes all active network sessions to drop immediately. Because of this, file downloads fail, SSH sessions close, online games freeze, and business applications lose connection.

**The APTCP protocol solves this problem:**
* If the physical connection is lost, NekoFlow does not terminate the connection on your applications' side. It puts it into a suspended waiting state.
* As soon as connection is restored (even if your IP address has changed), NekoFlow seamlessly resumes data transmission from the exact point it was interrupted.
* For your applications, this process is entirely invisible — no crashes, no connection errors, and no interrupted sessions.

---

## Quick Start: How to Run the Program?

To launch the graphical interface, execute the **`NekoFlow.exe`** file in the root directory.

* **Important:** For the network tunnel to operate fully (TUN Mode), you must run the program **as Administrator**, as the operating system requires corresponding privileges to configure the virtual network adapter and modify Windows routing tables.

---

## Configuring Traffic Interception Modes

The application offers two operation modes depending on your tasks:

### Mode A: Global Network Tunnel (TUN Mode)
In this mode, traffic is automatically intercepted on the level of the entire operating system using a virtual network adapter named `Wintun`.

1. Run `NekoFlow.exe` as Administrator.
2. Select **TUN Mode**.
3. (Optional) Activate **Split Tunneling** if you only want traffic from specific applications (e.g., `chrome.exe` or `discord.exe`) to flow through the secure channel. The application lists can be customized via the "Application List..." button.
4. Toggle the main switch on.

*Note: If the Wintun virtual adapter fails to initialize on the first try (a Windows OS quirk regarding driver resource release), simply restart NekoFlow completely and try to connect again.*

### Mode B: Local Proxy Server (SOCKS Proxy) + Proxifier
In this mode, NekoFlow does not modify system routing tables or virtual interfaces; instead, it hosts an anonymous local SOCKS5 proxy server on port **`3080`**.

To route traffic from your chosen applications through this port, utilize the **Proxifier** utility:
1. Start NekoFlow in **SOCKS Proxy** mode and activate the connection.
2. Open **Proxifier** -> **Profile** -> **Proxy Servers...**
3. Click **Add** and specify the local proxy server parameters:
   * **Address:** `127.0.0.1`
   * **Port:** `3080`
   * **Protocol:** `SOCKS Version 5`
   * **Authentication:** Uncheck (anonymous access, no username or password required).
4. Click **OK** and configure your Proxification Rules for the desired applications.

---

## Configuring TLS Encryption

To secure the transmitted data from unauthorized modifications within the transit channel, the APTCP protocol supports TLS encryption:

1. If TLS encryption was enabled during server setup, retrieve the public certificate file **`cert.pem`** from your server.
2. Create a folder named **`tls`** in the NekoFlow root directory (if it does not exist yet) and copy the certificate file into it.
3. In NekoFlow, open the **"Server Management"** menu, select your server, tick **"Use TLS"**, and specify the path to your `.pem` file via the `...` file selection button.
4. Click the **"Test"** button to ensure that the encryption handshake completes successfully and communication is established.

---

## Deploying Your Own Server

The client only works when connected to your own remote server. The server-side component is deployed in a Linux environment via Docker.

* **Server Repository:** [APTCP-SOCKS](https://github.com/Doctorgth/APTCP-SOCKS)
* **Minimum Requirements:** `docker` and `docker-compose` utilities installed on the server.

### One-liner Server Installation Command:
Execute this command in your Linux server terminal to automatically compile and run the container:
```bash
curl -O https://raw.githubusercontent.com/Doctorgth/APTCP-SOCKS/main/install.sh && sed -i 's/\r//' install.sh && chmod +x install.sh && ./install.sh
```
During installation, the script will prompt for the port, username, password, generate the required encryption keys, and deploy the server container in the background.