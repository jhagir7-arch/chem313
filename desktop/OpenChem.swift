import AppKit
import WebKit

final class DesktopApp: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate, WKScriptMessageHandler, NSMenuItemValidation {
    var window: NSWindow!
    var web: WKWebView!
    var worker: Process?
    var localURL: URL?
    var output = Data()
    var logHandle: FileHandle?
    var smokeTimer: Timer?
    var smokeTicks = 0
    private let frontendCommands: Set<String> = [
        "new-project", "open-structure", "save-structure", "export-mol",
        "structures", "orcaInput", "orca", "measurements", "science", "notes", "history", "connections", "recipes",
        "toggle-assistant", "generate-3d", "check-engines", "help"
    ]
    private var menuQARoutes = [String]()

    func applicationDidFinishLaunching(_ notification: Notification) {
        makeMenu()
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1440, height: 940), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "OpenChem"
        window.minSize = NSSize(width: 850, height: 650)
        window.center()
        window.setFrameAutosaveName("OpenChemMainWindow")
        window.collectionBehavior.insert(.fullScreenPrimary)
        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(self, name: "desktop")
        web = WKWebView(frame: window.contentView!.bounds, configuration: configuration)
        web.autoresizingMask = [.width, .height]
        web.uiDelegate = self
        web.navigationDelegate = self
        let loading = NSView(frame: web.frame)
        let label = NSTextField(labelWithString: "Starting local scientific engines…")
        label.font = .systemFont(ofSize: 18, weight: .medium)
        label.alignment = .center
        label.frame = NSRect(x: 0, y: loading.bounds.midY, width: loading.bounds.width, height: 30)
        label.autoresizingMask = [.width, .minYMargin, .maxYMargin]
        loading.addSubview(label)
        window.contentView = loading
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        startWorker()
    }

    func makeMenu() {
        let menu = NSMenu()
        let appItem = NSMenuItem(title: "OpenChem", action: nil, keyEquivalent: "")
        menu.addItem(appItem)
        let appMenu = NSMenu(title: "OpenChem")
        let aboutItem = appMenu.addItem(withTitle: "About OpenChem", action: #selector(about), keyEquivalent: "")
        aboutItem.target = self
        appMenu.addItem(.separator())
        let servicesMenu = NSMenu(title: "Services")
        let servicesItem = NSMenuItem(title: "Services", action: nil, keyEquivalent: "")
        servicesItem.submenu = servicesMenu
        appMenu.addItem(servicesItem)
        NSApp.servicesMenu = servicesMenu
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Hide OpenChem", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        let hideOthers = appMenu.addItem(withTitle: "Hide Others", action: #selector(NSApplication.hideOtherApplications(_:)), keyEquivalent: "h")
        hideOthers.keyEquivalentModifierMask = [.command, .option]
        appMenu.addItem(withTitle: "Show All", action: #selector(NSApplication.unhideAllApplications(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit OpenChem", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu

        let fileItem = NSMenuItem(title: "File", action: nil, keyEquivalent: "")
        let fileMenu = NSMenu(title: "File")
        addFrontendItem(to: fileMenu, title: "New Project", command: "new-project", key: "n", modifiers: [.command, .shift])
        addFrontendItem(to: fileMenu, title: "Open Structure…", command: "open-structure", key: "o", modifiers: .command)
        fileMenu.addItem(.separator())
        addFrontendItem(to: fileMenu, title: "Save Structure", command: "save-structure", key: "s", modifiers: .command)
        addFrontendItem(to: fileMenu, title: "Export MOL…", command: "export-mol", key: "s", modifiers: [.command, .shift])
        fileMenu.addItem(.separator())
        fileMenu.addItem(withTitle: "Close Window", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        fileItem.submenu = fileMenu
        menu.addItem(fileItem)

        let edit = NSMenuItem(title: "Edit", action: nil, keyEquivalent: ""); menu.addItem(edit)
        let editMenu = NSMenu(title: "Edit")
        for (title, action, key) in [("Undo", "undo:", "z"), ("Redo", "redo:", "Z"), ("Cut", "cut:", "x"), ("Copy", "copy:", "c"), ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")] {
            editMenu.addItem(withTitle: title, action: Selector(action), keyEquivalent: key)
        }
        edit.submenu = editMenu

        let viewItem = NSMenuItem(title: "View", action: nil, keyEquivalent: "")
        let viewMenu = NSMenu(title: "View")
        for (title, command, key) in [("Structure", "structures", "1"), ("Calculation Input", "orcaInput", "2"), ("Results", "orca", "3"), ("Measurements", "measurements", "4"), ("Scientific Tools", "science", "5"), ("Research Scripts", "recipes", "6"), ("Notebook", "notes", "7"), ("Project Files", "history", "8"), ("Engine Status", "connections", "9")] {
            addFrontendItem(to: viewMenu, title: title, command: command, key: key, modifiers: .command)
        }
        viewMenu.addItem(.separator())
        addFrontendItem(to: viewMenu, title: "Qwen Assistant", command: "toggle-assistant", key: "a", modifiers: [.command, .shift])
        viewMenu.addItem(.separator())
        addNativeItem(to: viewMenu, title: "Zoom In", action: #selector(zoomIn(_:)), key: "+", modifiers: .command)
        addNativeItem(to: viewMenu, title: "Zoom Out", action: #selector(zoomOut(_:)), key: "-", modifiers: .command)
        addNativeItem(to: viewMenu, title: "Actual Size", action: #selector(resetZoom(_:)), key: "0", modifiers: .command)
        viewItem.submenu = viewMenu
        menu.addItem(viewItem)

        let calculationItem = NSMenuItem(title: "Calculation", action: nil, keyEquivalent: "")
        let calculationMenu = NSMenu(title: "Calculation")
        addFrontendItem(to: calculationMenu, title: "Generate 3D", command: "generate-3d")
        addFrontendItem(to: calculationMenu, title: "Prepare ORCA", command: "orcaInput")
        calculationMenu.addItem(.separator())
        addFrontendItem(to: calculationMenu, title: "Check Engines", command: "check-engines")
        calculationItem.submenu = calculationMenu
        menu.addItem(calculationItem)

        let windowItem = NSMenuItem(title: "Window", action: nil, keyEquivalent: "")
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(withTitle: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windowMenu.addItem(withTitle: "Zoom", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: "")
        windowMenu.addItem(withTitle: "Bring All to Front", action: #selector(NSApplication.arrangeInFront(_:)), keyEquivalent: "")
        NSApp.windowsMenu = windowMenu
        windowItem.submenu = windowMenu
        menu.addItem(windowItem)

        let helpItem = NSMenuItem(title: "Help", action: nil, keyEquivalent: "")
        let helpMenu = NSMenu(title: "Help")
        addFrontendItem(to: helpMenu, title: "OpenChem Guide", command: "help")
        NSApp.helpMenu = helpMenu
        helpItem.submenu = helpMenu
        menu.addItem(helpItem)
        NSApp.mainMenu = menu
        recordMenuQA()
    }

    func addFrontendItem(to menu: NSMenu, title: String, command: String, key: String = "", modifiers: NSEvent.ModifierFlags = []) {
        let item = NSMenuItem(title: title, action: #selector(sendFrontendCommand(_:)), keyEquivalent: key)
        item.keyEquivalentModifierMask = modifiers
        item.target = self
        item.representedObject = command
        menu.addItem(item)
    }

    func addNativeItem(to menu: NSMenu, title: String, action: Selector, key: String, modifiers: NSEvent.ModifierFlags) {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: key)
        item.keyEquivalentModifierMask = modifiers
        item.target = self
        menu.addItem(item)
    }

    var hasValidatedBridge: Bool {
        guard let expected = localURL, let current = web?.url else { return false }
        return current.host == "127.0.0.1" && current.port == expected.port
    }

    func validateMenuItem(_ menuItem: NSMenuItem) -> Bool {
        if menuItem.action == #selector(sendFrontendCommand(_:)) || menuItem.action == #selector(zoomIn(_:)) || menuItem.action == #selector(zoomOut(_:)) || menuItem.action == #selector(resetZoom(_:)) {
            return hasValidatedBridge
        }
        return true
    }

    @objc func sendFrontendCommand(_ sender: NSMenuItem) {
        guard let command = sender.representedObject as? String, frontendCommands.contains(command), hasValidatedBridge else { return }
        let event = "window.dispatchEvent(new CustomEvent('openchem:command',{detail:\(javaScriptLiteral(command))}))"
        web.evaluateJavaScript(event)
        menuQARoutes.append(command)
        recordMenuQA()
    }

    @objc func zoomIn(_ sender: Any?) { guard hasValidatedBridge else { return }; web.magnification = min(web.magnification + 0.1, 3.0) }
    @objc func zoomOut(_ sender: Any?) { guard hasValidatedBridge else { return }; web.magnification = max(web.magnification - 0.1, 0.5) }
    @objc func resetZoom(_ sender: Any?) { guard hasValidatedBridge else { return }; web.magnification = 1.0 }

    func javaScriptLiteral(_ value: String) -> String {
        let data = try? JSONSerialization.data(withJSONObject: [value])
        let array = data.flatMap { String(data: $0, encoding: .utf8) } ?? "[\"\"]"
        return String(array.dropFirst().dropLast())
    }

    func recordMenuQA() {
        guard let path = ProcessInfo.processInfo.environment["OPENCHEM_MENU_QA_RESULT"] else { return }
        func titles(in menu: NSMenu) -> [String] { menu.items.flatMap { [$0.title] + ($0.submenu.map(titles(in:)) ?? []) } }
        let evidence: [String: Any] = ["menuTitles": titles(in: NSApp.mainMenu ?? NSMenu()), "routedCommands": menuQARoutes]
        guard let data = try? JSONSerialization.data(withJSONObject: evidence, options: [.prettyPrinted, .sortedKeys]) else { return }
        try? data.write(to: URL(fileURLWithPath: path), options: .atomic)
    }

    func frontendMenuItem(for command: String, in menu: NSMenu) -> (menu: NSMenu, index: Int)? {
        for (index, item) in menu.items.enumerated() {
            if item.representedObject as? String == command { return (menu, index) }
            if let submenu = item.submenu, let found = frontendMenuItem(for: command, in: submenu) { return found }
        }
        return nil
    }

    // Package QA only: actions use NSMenu's normal dispatch path after smoke confirms the UI listener is loaded.
    func runMenuQACommands(_ rawCommands: String, completion: @escaping () -> Void) {
        let commands = rawCommands.split(separator: ",").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { frontendCommands.contains($0) }
        func invoke(_ index: Int) {
            guard index < commands.count else { completion(); return }
            guard let item = frontendMenuItem(for: commands[index], in: NSApp.mainMenu ?? NSMenu()) else {
                DispatchQueue.main.async { invoke(index + 1) }
                return
            }
            item.menu.performActionForItem(at: item.index)
            DispatchQueue.main.async { invoke(index + 1) }
        }
        invoke(0)
    }

    @objc func about() {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "Development"
        let credits = "A local chemistry workbench. Structures, reviewed calculation inputs and immutable research records. Optional engines, Avogadro and Qwen require separate local installation. ORCA requires a separately licensed executable. See the distribution README and third-party notices for scope and validation limits."
        NSApp.orderFrontStandardAboutPanel(options: [.applicationName: "OpenChem", .applicationVersion: version, .credits: NSAttributedString(string: credits)])
    }

    // The public shell distributes our native executable only. Dependencies and
    // generated browser assets stay in the user's separately installed checkout.
    func externalSourceRoot() -> URL? {
        let env = ProcessInfo.processInfo.environment["OPENCHEM_SOURCE_ROOT"]
        let saved = UserDefaults.standard.string(forKey: "OpenChemSourceRoot")
        func ready(_ root: URL) -> Bool {
            FileManager.default.isExecutableFile(atPath: root.appendingPathComponent(".venv/bin/python").path)
                && FileManager.default.fileExists(atPath: root.appendingPathComponent("frontend/dist/index.html").path)
                && FileManager.default.fileExists(atPath: root.appendingPathComponent("backend/src/hypothesislab/desktop.py").path)
        }
        if let path = env ?? saved {
            let root = URL(fileURLWithPath: path, isDirectory: true)
            if ready(root) { return root }
            if env != nil { fail("OPENCHEM_SOURCE_ROOT needs a configured OpenChem checkout. Run bash scripts/setup_public_runtime.sh there first."); return nil }
        }
        let panel = NSOpenPanel()
        panel.title = "Choose your installed OpenChem source folder"
        panel.message = "First run bash scripts/setup_public_runtime.sh in the downloaded source folder. Then choose that folder here. The native shell does not bundle Python, engines, browser dependencies or models."
        panel.canChooseDirectories = true; panel.canChooseFiles = false; panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let root = panel.url else { NSApp.terminate(nil); return nil }
        guard ready(root) else { fail("This folder is not ready. Run bash scripts/setup_public_runtime.sh in the OpenChem source folder, then reopen OpenChem."); return nil }
        UserDefaults.standard.set(root.path, forKey: "OpenChemSourceRoot")
        return root
    }

    func startWorker() {
        guard let resources = Bundle.main.resourceURL else { fail("Application resources are missing."); return }
        let dataRoot = ProcessInfo.processInfo.environment["OPENCHEM_DATA"] ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/OpenChem").path
        do {
            try FileManager.default.createDirectory(atPath: dataRoot, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            let log = URL(fileURLWithPath: dataRoot).appendingPathComponent("desktop.log")
            if !FileManager.default.fileExists(atPath: log.path) { FileManager.default.createFile(atPath: log.path, contents: nil, attributes: [.posixPermissions: 0o600]) }
            logHandle = try FileHandle(forWritingTo: log)
            try logHandle?.seekToEnd()
            let child = Process()
            if Bundle.main.object(forInfoDictionaryKey: "OpenChemExternalRuntime") as? Bool == true {
                guard let root = externalSourceRoot() else { return }
                child.executableURL = root.appendingPathComponent(".venv/bin/python")
                child.currentDirectoryURL = root
                child.arguments = ["-m", "hypothesislab.desktop", "--ui", root.appendingPathComponent("frontend/dist").path, "--data", dataRoot]
            } else {
                child.executableURL = resources.appendingPathComponent("engine/openchem-engine")
                child.arguments = ["--data", dataRoot]
            }
            let pipe = Pipe()
            child.standardOutput = pipe
            child.standardError = logHandle
            child.terminationHandler = { [weak self] task in
                DispatchQueue.main.async { if NSApp.isRunning && task.terminationStatus != 0 { self?.fail("The local engine stopped. See desktop.log in the project storage folder.") } }
            }
            pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
                let chunk = handle.availableData
                if chunk.isEmpty { handle.readabilityHandler = nil; return }
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    self.output.append(chunk)
                    guard self.localURL == nil, let firstLine = String(data: self.output, encoding: .utf8)?.split(separator: "\n").first,
                          let lineData = firstLine.data(using: .utf8),
                          let ready = try? JSONSerialization.jsonObject(with: lineData) as? [String: Any],
                          let urlText = ready["url"] as? String, let url = URL(string: urlText), url.host == "127.0.0.1" else { return }
                    self.localURL = url
                    self.window.contentView = self.web
                    self.web.load(URLRequest(url: url))
                }
            }
            worker = child
            try child.run()
        } catch { fail("Could not start the local scientific engine: \(error.localizedDescription)") }
    }

    func fail(_ text: String) {
        let alert = NSAlert(); alert.messageText = "OpenChem needs attention"; alert.informativeText = text; alert.runModal()
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationWillTerminate(_ notification: Notification) {
        smokeTimer?.invalidate()
        worker?.terminationHandler = nil
        if worker?.isRunning == true { worker?.terminate() }
        try? logHandle?.close()
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let target = navigationAction.request.url else { decisionHandler(.cancel); return }
        if target.scheme == "about" || (target.host == "127.0.0.1" && target.port == localURL?.port) { decisionHandler(.allow) }
        else { decisionHandler(.cancel) }
    }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel(); panel.allowsMultipleSelection = parameters.allowsMultipleSelection; panel.canChooseDirectories = false
        panel.beginSheetModal(for: window) { completionHandler($0 == .OK ? panel.urls : nil) }
    }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = NSAlert(); alert.messageText = message; alert.beginSheetModal(for: window) { _ in completionHandler() }
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = NSAlert(); alert.messageText = message; alert.addButton(withTitle: "Continue"); alert.addButton(withTitle: "Cancel"); alert.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn) }
    }
    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let alert = NSAlert(); alert.messageText = prompt
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 320, height: 26)); field.stringValue = defaultText ?? ""
        alert.accessoryView = field; alert.addButton(withTitle: "Create project"); alert.addButton(withTitle: "Cancel")
        alert.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn ? field.stringValue : nil) }
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, message.frameInfo.securityOrigin.host == "127.0.0.1",
              message.frameInfo.securityOrigin.port == localURL?.port,
              let body = message.body as? [String: String], body["action"] == "save",
              let encoded = body["base64"], let bytes = Data(base64Encoded: encoded), bytes.count <= 30_000_000,
              let proposed = body["name"] else { return }
        let panel = NSSavePanel(); panel.nameFieldStringValue = URL(fileURLWithPath: proposed).lastPathComponent
        panel.beginSheetModal(for: window) { result in
            guard result == .OK, let target = panel.url else { return }
            do { try bytes.write(to: target, options: .atomic) } catch { self.fail("Could not save: \(error.localizedDescription)") }
        }
    }

    // Run only when explicitly selected by our local package-verification script.
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard let destination = ProcessInfo.processInfo.environment["OPENCHEM_SMOKE_RESULT"] else { return }
        smokeTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] timer in
            guard let self = self else { timer.invalidate(); return }
            self.smokeTicks += 1
            self.web.evaluateJavaScript("JSON.stringify({title:document.title,connected:document.querySelector('.engine-state')?.textContent.includes('Local service connected'),formula:document.querySelector('.formula')?.textContent,editor:!!window.__openchemEditor,body:document.body.innerText.slice(0,3000),webgl:!!document.createElement('canvas').getContext('webgl2')})") { result, error in
                guard let text = result as? String, let data = text.data(using: .utf8) else { return }
                let response = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
                let workflowReady = response?["connected"] as? Bool == true && response?["editor"] as? Bool == true && response?["formula"] as? String == "C8H9NO2"
                if workflowReady || self.smokeTicks > 90 {
                    timer.invalidate()
                    let finishSmoke = { self.completeSmoke(destination: destination, data: data) }
                    if workflowReady, let commands = ProcessInfo.processInfo.environment["OPENCHEM_MENU_QA_COMMANDS"] {
                        self.runMenuQACommands(commands, completion: finishSmoke)
                    } else {
                        finishSmoke()
                    }
                }
            }
        }
    }

    func completeSmoke(destination: String, data: Data) {
        if let scriptPath = ProcessInfo.processInfo.environment["OPENCHEM_WORKFLOW_SCRIPT"],
           let script = try? String(contentsOfFile: scriptPath, encoding: .utf8) {
            runWorkflow(script, destination: destination)
            return
        }
        try? data.write(to: URL(fileURLWithPath: destination))
        web.takeSnapshot(with: nil) { image, _ in
            if let image = image, let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff), let png = bitmap.representation(using: .png, properties: [:]) {
                try? png.write(to: URL(fileURLWithPath: destination + ".png"))
            }
            if ProcessInfo.processInfo.environment["OPENCHEM_SMOKE_QUIT"] == "1" { NSApp.terminate(nil) }
        }
    }

    // Explicit verification hook: absent in ordinary launches, no model/tool authority.
    func runWorkflow(_ script: String, destination: String) {
        web.callAsyncJavaScript(script, arguments: [:], in: nil, in: .page) { result in
            let text: String
            switch result {
            case .success(let value): text = value as? String ?? "{\"status\":\"FAIL\",\"error\":\"No workflow result\"}"
            case .failure(let error):
                let object = ["status": "FAIL", "error": error.localizedDescription]
                text = String(data: (try? JSONSerialization.data(withJSONObject: object)) ?? Data(), encoding: .utf8) ?? "{}"
            }
            try? text.data(using: .utf8)?.write(to: URL(fileURLWithPath: destination))
            self.web.takeSnapshot(with: nil) { image, _ in
                if let image = image, let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff), let png = bitmap.representation(using: .png, properties: [:]) {
                    try? png.write(to: URL(fileURLWithPath: destination + ".png"))
                }
                if ProcessInfo.processInfo.environment["OPENCHEM_SMOKE_QUIT"] == "1" { NSApp.terminate(nil) }
            }
        }
    }

}

let application = NSApplication.shared
let delegate = DesktopApp()
application.delegate = delegate
application.setActivationPolicy(.regular)
application.run()
