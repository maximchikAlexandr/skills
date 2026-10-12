import AppKit
import Foundation

func fail(_ message: String) -> Never {
    fputs(message + "\n", stderr)
    exit(2)
}

guard CommandLine.arguments.count == 4 else {
    fail("Usage: swift render_terminal.swift <title> <input.txt> <output.png>")
}
let title = CommandLine.arguments[1]
let input = URL(fileURLWithPath: CommandLine.arguments[2]).standardizedFileURL
let output = URL(fileURLWithPath: CommandLine.arguments[3]).standardizedFileURL
guard input != output else { fail("Input and output must be different files") }
let contents = try String(contentsOf: input, encoding: .utf8)
let invalidControl = contents.unicodeScalars.contains {
    $0.value < 32 && $0.value != 9 && $0.value != 10
}
guard !invalidControl else {
    fail("Plain text required: ANSI escapes and carriage-return progress are unsupported")
}
// Expand tabs to terminal-style eight-column stops; preserve other text.
let rawLines = contents.components(separatedBy: "\n")
var lines = rawLines.map { line -> String in
    var result = ""
    var column = 0
    for character in line {
        if character == "\t" {
            let spaces = 8 - column % 8
            result += String(repeating: " ", count: spaces)
            column += spaces
        } else {
            result.append(character)
            column += 1
        }
    }
    return result
}
if lines.count > 1 && lines.last == "" { lines.removeLast() }
let font = NSFont.monospacedSystemFont(ofSize: 17, weight: .regular)
let attrs: [NSAttributedString.Key: Any] = [
    .font: font,
    .foregroundColor: NSColor(calibratedRed: 0.88, green: 0.92, blue: 0.96, alpha: 1)
]
let titleAttrs: [NSAttributedString.Key: Any] = [
    .font: NSFont.monospacedSystemFont(ofSize: 18, weight: .semibold),
    .foregroundColor: NSColor.white
]
let lineHeight: CGFloat = 25
let textWidth = lines.map { ($0 as NSString).size(withAttributes: attrs).width }.max() ?? 0
let titleWidth = (title as NSString).size(withAttributes: titleAttrs).width
let width = max(480, ceil(max(textWidth, titleWidth)) + 64)
let height = CGFloat(lines.count) * lineHeight + 110
guard width <= 12000 && height <= 12000 && width * height <= 40_000_000 else {
    fail("Output is too large; capture a bounded, explicitly labelled excerpt")
}
let image = NSImage(size: NSSize(width: width, height: height))
image.lockFocus()
NSColor(calibratedRed: 0.06, green: 0.09, blue: 0.14, alpha: 1).setFill()
NSRect(x: 0, y: 0, width: width, height: height).fill()
NSColor(calibratedRed: 0.12, green: 0.17, blue: 0.24, alpha: 1).setFill()
NSRect(x: 0, y: height - 64, width: width, height: 64).fill()
(title as NSString).draw(at: NSPoint(x: 28, y: height - 43), withAttributes: titleAttrs)
for (index, line) in lines.enumerated() {
    (line as NSString).draw(
        at: NSPoint(x: 28, y: height - 93 - CGFloat(index) * lineHeight),
        withAttributes: attrs
    )
}
image.unlockFocus()
guard let tiff = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiff),
      let png = bitmap.representation(using: .png, properties: [:]) else {
    fail("Could not render PNG")
}
try png.write(to: output, options: .atomic)
