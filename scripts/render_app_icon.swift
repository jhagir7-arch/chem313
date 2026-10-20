// Original OpenChem identity. Rebuild: swift scripts/render_app_icon.swift
import AppKit
import Foundation

let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let work = FileManager.default.temporaryDirectory.appendingPathComponent("openchem-icon-\(UUID().uuidString)")
defer { try? FileManager.default.removeItem(at: work) }
let iconset = work.appendingPathComponent("OpenChem.iconset")
try FileManager.default.createDirectory(at: iconset, withIntermediateDirectories: true)

func render(_ size: Int) throws -> Data {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    let graphics = NSGraphicsContext(bitmapImageRep: bitmap)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = graphics
    let c = graphics.cgContext
    c.scaleBy(x: CGFloat(size)/1024, y: CGFloat(size)/1024)
    // Quiet, high-contrast instrument tile with a chemical-bond C and open O atom.
    c.setFillColor(NSColor(calibratedWhite: 0.055, alpha: 1).cgColor)
    c.addPath(CGPath(roundedRect: CGRect(x: 64, y: 64, width: 896, height: 896),
        cornerWidth: 192, cornerHeight: 192, transform: nil))
    c.fillPath()
    c.setStrokeColor(NSColor(calibratedWhite: 0.97, alpha: 1).cgColor)
    c.setLineWidth(54)
    c.setLineCap(.round)
    c.setLineJoin(.round)
    // Open hexagonal contour; deliberately a mark, not a claimed molecule.
    c.move(to: CGPoint(x: 665, y: 648))
    c.addLine(to: CGPoint(x: 512, y: 736))
    c.addLine(to: CGPoint(x: 304, y: 616))
    c.addLine(to: CGPoint(x: 304, y: 376))
    c.addLine(to: CGPoint(x: 512, y: 256))
    c.addLine(to: CGPoint(x: 720, y: 376))
    c.strokePath()
    c.setLineWidth(43)
    c.strokeEllipse(in: CGRect(x: 657, y: 553, width: 126, height: 126))
    c.setFillColor(NSColor(calibratedWhite: 0.97, alpha: 1).cgColor)
    c.fillEllipse(in: CGRect(x: 693, y: 349, width: 54, height: 54))
    NSGraphicsContext.restoreGraphicsState()
    return bitmap.representation(using: .png, properties: [:])!
}
for base in [16, 32, 128, 256, 512] {
    try render(base).write(to: iconset.appendingPathComponent("icon_\(base)x\(base).png"))
    try render(base*2).write(to: iconset.appendingPathComponent("icon_\(base)x\(base)@2x.png"))
}
try render(1024).write(to: root.appendingPathComponent("desktop/branding/OpenChem.png"))
let task = Process()
task.executableURL = URL(fileURLWithPath: "/usr/bin/iconutil")
task.arguments = ["-c", "icns", iconset.path, "-o", root.appendingPathComponent("desktop/OpenChem.icns").path]
try task.run(); task.waitUntilExit()
guard task.terminationStatus == 0 else { fatalError("iconutil failed") }
print("Rendered OpenChem icon at all macOS sizes.")
