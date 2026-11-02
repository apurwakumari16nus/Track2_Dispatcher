import SwiftUI
import UIKit

extension UIColor {
    convenience init(hex: UInt32) {
        self.init(red: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255, blue: CGFloat(hex & 0xFF) / 255, alpha: 1)
    }
}

extension Color {
    init(light: UInt32, dark: UInt32) {
        self.init(uiColor: UIColor { $0.userInterfaceStyle == .dark ? UIColor(hex: dark) : UIColor(hex: light) })
    }
}

/// Light canvas, white cards, navy ink. The deck colours are accents only. Green is kept for one thing:
/// something a person confirmed. Engine checks and system states use teal or neutral.
enum Ink {
    static let canvas = Color(light: 0xF6F8FB, dark: 0x0B1016)
    static let card = Color(light: 0xFFFFFF, dark: 0x141B23)
    static let well = Color(light: 0xEEF2F6, dark: 0x1D2630)
    static let line = Color(light: 0xE4E9EF, dark: 0x25303C)
    static let primary = Color(light: 0x142334, dark: 0xEEF2F6)
    static let secondary = Color(light: 0x5D6C7B, dark: 0x9FAEBC)
    static let tertiary = Color(light: 0x83919E, dark: 0x6F7E8C)
    static let cyan = Color(light: 0x14A5B0, dark: 0x3ACED8)
    static let teal = Color(light: 0x128F7E, dark: 0x20BFA9)
    static let cobalt = Color(light: 0x4562E0, dark: 0x7A95F7)
    static let amber = Color(light: 0xA36A0B, dark: 0xE8A53A)
    static let amberWash = Color(light: 0xFCF3E1, dark: 0x2B2212)
    static let coral = Color(light: 0xC8443C, dark: 0xEA665E)
    static let coralWash = Color(light: 0xFDECEA, dark: 0x301A18)
    static let human = Color(light: 0x1F8F57, dark: 0x3CC581)
    static let humanWash = Color(light: 0xE6F6EC, dark: 0x13291D)
    static let cardFoot = Color(light: 0xF7F9FD, dark: 0x10161D)
    static let edge = Color(light: 0xFFFFFF, dark: 0x2C3846)
    static let glowCyan = Color(light: 0xD6F1F4, dark: 0x0E2B33)
    static let glowViolet = Color(light: 0xE2E6FC, dark: 0x171D40)
    static let thread = LinearGradient(colors: [Color(light: 0x3ACED8, dark: 0x3ACED8), Color(light: 0x20BFA9, dark: 0x20BFA9), Color(light: 0x5677F3, dark: 0x5677F3)],
                                       startPoint: .leading, endPoint: .trailing)
    static let press = LinearGradient(colors: [Color(hex: 0x5B7DF6), Color(hex: 0x3353D8)], startPoint: .topLeading, endPoint: .bottomTrailing)
    static let chosen = LinearGradient(colors: [Color(hex: 0x1FA7B8), Color(hex: 0x3A5FE0)], startPoint: .topLeading, endPoint: .bottomTrailing)
}

/// Cloth out of the dye vat. Each screen has one piece of it, behind the sentence that matters most.
/// Dark mode uses a deeper, quieter batch of the same dye, so it glows rather than shouts.
enum Dye {
    case thread, alarm

    fileprivate func colours(deep: Bool) -> [Color] {
        let hex: [UInt32] = switch (self, deep) {
        case (.thread, false):
            [0x0E1C30, 0x14305C, 0x2A49C6, 0x11243C, 0x2343B4, 0x128F90, 0x142A52, 0x12687E, 0x1B8FA3]
        case (.thread, true):
            [0x0D1828, 0x121D45, 0x1C2C7C, 0x0E1A2C, 0x182870, 0x0D5560, 0x0F1D38, 0x0D4656, 0x116C7C]
        case (.alarm, false):
            [0x241225, 0x431A38, 0xA8344A, 0x2C1530, 0x6F2240, 0xC94C3E, 0x37172F, 0x842A44, 0xD9743C]
        case (.alarm, true):
            [0x1C0F1E, 0x32152B, 0x74283A, 0x221126, 0x4E1A31, 0x883830, 0x28112A, 0x581F34, 0x934C2E]
        }
        return hex.map { Color(hex: $0) }
    }

    var glow: Color { self == .thread ? Color(hex: 0x2A49C6) : Color(hex: 0xA8344A) }
}

/// The dyed cloth itself. It holds still: nothing on it changes, so the phone draws it once.
struct DyeField: View {
    var dye: Dye = .thread
    var deep = false

    var body: some View {
        MeshGradient(width: 3, height: 3, points: [
            SIMD2(0, 0), SIMD2(0.5, 0), SIMD2(1, 0),
            SIMD2(0, 0.5), SIMD2(0.5, 0.5), SIMD2(1, 0.5),
            SIMD2(0, 1), SIMD2(0.5, 1), SIMD2(1, 1)
        ], colors: dye.colours(deep: deep))
    }
}

/// The finest visible weave, so a page reads as cloth rather than plastic. One small tile, drawn once and repeated.
private enum Twill {
    static let tile: UIImage = UIGraphicsImageRenderer(size: CGSize(width: 8, height: 8)).image { context in
        UIColor.black.setFill()
        for step in 0 ..< 4 {
            context.fill(CGRect(x: step * 2, y: 6 - step * 2, width: 1, height: 1))
        }
    }
}

/// Behind every screen. By day the canvas with a little colour rising from the top. By night a deep indigo and teal,
/// dim enough that the cards above it carry the light.
struct Backdrop: View {
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        ZStack(alignment: .top) {
            if scheme == .dark {
                Color(hex: 0x0A1118)
                RadialGradient(colors: [Color(hex: 0x1C2352), .clear], center: .topTrailing, startRadius: 0, endRadius: 560)
                RadialGradient(colors: [Color(hex: 0x0E2A33), .clear], center: .bottomLeading, startRadius: 0, endRadius: 480)
            } else {
                Ink.canvas
                LinearGradient(colors: [Ink.glowCyan, Ink.glowViolet], startPoint: .topLeading, endPoint: .trailing)
                    .frame(height: 460)
                    .mask(LinearGradient(colors: [.black, .black.opacity(0.75), .clear], startPoint: .top, endPoint: .bottom))
            }
            Image(uiImage: Twill.tile)
                .resizable(resizingMode: .tile)
                .renderingMode(.template)
                .foregroundStyle(.primary)
                .opacity(scheme == .dark ? 0.05 : 0.04)
                .allowsHitTesting(false)
                .accessibilityHidden(true)
        }
        .ignoresSafeArea()
    }
}

/// One colour, one symbol and one name for each point in an order's life. Telegram uses the same names in the same order.
/// The cool colours walk from violet towards green as a batch gets closer to home. Warm colours always mean a problem,
/// and green is only reached when a person has checked the batch in.
enum Stage: Int, CaseIterable, Identifiable {
    case review, sent, accepted, sewing, completed, back

    var id: Int { rawValue }
    var name: String { ["In review", "Sent", "Accepted", "Sewing", "Completed", "Back"][rawValue] }
    var meaning: String {
        ["Waiting for your decision", "Waiting for the workshop to accept", "Accepted, not started yet", "Being made at the workshop",
         "Finished at the workshop, which is free for new work", "Received and checked in"][rawValue]
    }
    var symbol: String { ["text.magnifyingglass", "paperplane.fill", "hand.thumbsup.fill", "scissors", "shippingbox.fill", "checkmark"][rawValue] }

    var color: Color {
        [Color(light: 0x5D6C7B, dark: 0xA9B6C4), Color(light: 0x7452D6, dark: 0xA88BFA), Color(light: 0x3F5FE0, dark: 0x7E9AF9),
         Color(light: 0x0B8CA2, dark: 0x3ACED8), Color(light: 0x0F8F7C, dark: 0x2BD0B4), Ink.human][rawValue]
    }

    var gradient: LinearGradient {
        let hex: [UInt32] = [[0x93A1B0, 0x5D6C7B], [0xA98BFA, 0x6C47D6], [0x6F8DF8, 0x3353D8], [0x45D2DE, 0x0E8CA6], [0x34D6BA, 0x0F8F7C], [0x4BD08C, 0x1F8F57]][rawValue]
        return LinearGradient(colors: hex.map { Color(hex: $0) }, startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    /// A status line from a workshop's tap, read back into a stage.
    init?(status text: String) {
        let found: [(String, Stage)] = [("Accepted", .accepted), ("In production", .sewing), ("Completed", .completed), ("On its way", .completed), ("Received", .back)]
        guard let match = found.first(where: { text.hasPrefix($0.0) }) else { return nil }
        self = match.1
    }
}

/// A stage's symbol in its colour. It is never colour alone: the symbol and the name always travel with it.
struct StageBadge: View {
    var stage: Stage
    var size: CGFloat = 30
    var lit = true
    @Environment(\.onCloth) private var onCloth

    var body: some View {
        Image(systemName: stage.symbol)
            .font(.system(size: size * 0.42, weight: .bold))
            .foregroundStyle(lit ? .white : onCloth ? .white.opacity(0.6) : Ink.tertiary)
            .frame(width: size, height: size)
            .background {
                if lit {
                    Circle().fill(stage.gradient)
                } else {
                    Circle().fill(onCloth ? AnyShapeStyle(.white.opacity(0.14)) : AnyShapeStyle(Ink.well))
                }
            }
            .accessibilityHidden(true)
    }
}

/// The whole pipeline in one row: every stage with its count, joined by a stitch. Tap one to see those orders.
struct StageLine: View {
    var counts: [Stage: Int]
    var selected: Stage?
    var pick: (Stage) -> Void
    @Environment(\.onCloth) private var onCloth

    var body: some View {
        ZStack(alignment: .top) {
            Stitches(width: 2, colour: onCloth ? .white.opacity(0.3) : Ink.line).padding(.horizontal, 28).padding(.top, 15)
            HStack(alignment: .top, spacing: 0) {
                ForEach(Stage.allCases) { stage in
                    let count = counts[stage] ?? 0
                    Button { pick(stage) } label: {
                        VStack(spacing: 3) {
                            StageBadge(stage: stage, size: 32, lit: count > 0)
                            Text("\(count)").font(.headline).monospacedDigit().foregroundStyle(onCloth ? .white : Ink.primary).contentTransition(.numericText())
                            Text(stage.name).font(.system(size: 10.5, weight: .medium)).foregroundStyle(onCloth ? .white.opacity(0.8) : Ink.secondary).lineLimit(1).minimumScaleFactor(0.75)
                        }
                        .frame(maxWidth: .infinity)
                        .contentShape(.rect)
                        .opacity(selected == nil || selected == stage ? 1 : 0.38)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("\(stage.name), \(count). \(stage.meaning)")
                    .accessibilityAddTraits(selected == stage ? .isSelected : [])
                }
            }
        }
    }
}

/// What each colour means, wherever batches are drawn without their names.
struct StageLegend: View {
    var stages: [Stage] = [.sent, .accepted, .sewing, .completed]

    var body: some View {
        FlowLayout(spacing: 10) {
            ForEach(stages) { stage in
                HStack(spacing: 4) {
                    Circle().fill(stage.gradient).frame(width: 8, height: 8)
                    Text(stage.name).font(.caption).foregroundStyle(Ink.secondary)
                }
            }
        }
    }
}

enum Tone: String {
    case risk, warn, info, good

    var color: Color {
        switch self {
        case .risk: Ink.coral
        case .warn: Ink.amber
        case .info: Ink.cobalt
        case .good: Ink.human
        }
    }

    var wash: Color {
        switch self {
        case .risk: Ink.coralWash
        case .warn: Ink.amberWash
        case .info: Ink.well
        case .good: Ink.humanWash
        }
    }

    var gradient: LinearGradient {
        let colours: [UInt32] = switch self {
        case .risk: [0xEE7A64, 0xC8443C]
        case .warn: [0xF2B552, 0xC98416]
        case .info: [0x35C4D6, 0x5677F3]
        case .good: [0x3CC581, 0x1F8F57]
        }
        return LinearGradient(colors: colours.map { Color(hex: $0) }, startPoint: .topLeading, endPoint: .bottomTrailing)
    }
}

extension Font {
    /// New York, for the one sentence on each screen that matters. Everything else stays in the system face.
    /// The one big sentence on a screen. It grows with text size, more gently than body text, so it still fits.
    static func hero(_ size: CGFloat) -> Font { .system(size: UIFontMetrics(forTextStyle: .title1).scaledValue(for: size, compatibleWith: .current).clamped(to: size ... size * 1.3), weight: .medium, design: .serif) }
    static let label = Font.footnote.weight(.semibold)
}

/// A card's surface. Paper by day, smoked glass by night. Cards sit on a still background, so a live blur on each one
/// would cost frames and show nothing. The tab bar and buttons keep real glass, where content does pass behind them.
struct Surface: View {
    var tint: Color?
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        let dark = scheme == .dark
        ZStack {
            if dark {
                LinearGradient(colors: [Color(hex: 0x2F3B58), Color(hex: 0x1E2B3A)], startPoint: .topLeading, endPoint: .bottomTrailing)
            } else {
                LinearGradient(colors: [Ink.card, Ink.cardFoot], startPoint: .top, endPoint: .bottom)
            }
            if let tint {
                RadialGradient(colors: [tint.opacity(dark ? 0.22 : 0.17), tint.opacity(0)], center: .topTrailing, startRadius: 0, endRadius: 270)
            }
        }
    }
}

extension View {
    /// The edge and the shadow. The shadow belongs to the card's shape, not its text, so scrolling does not redraw it.
    func hairline(_ shape: some InsettableShape, dark: Bool) -> some View {
        overlay(shape.strokeBorder(LinearGradient(colors: dark ? [.white.opacity(0.24), .white.opacity(0.05)] : [Ink.edge, Ink.line], startPoint: .top, endPoint: .bottom), lineWidth: 0.75))
            .background {
                if !dark { shape.fill(Ink.card).shadow(color: .black.opacity(0.05), radius: 10, y: 4) }
            }
    }
}

struct CardStyle: ViewModifier {
    var padding: CGFloat = 16
    var tint: Tone?
    @Environment(\.colorScheme) private var scheme

    func body(content: Content) -> some View {
        let shape = RoundedRectangle(cornerRadius: 22, style: .continuous)
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background { Surface(tint: tint?.color).clipShape(shape) }
            .hairline(shape, dark: scheme == .dark)
    }
}

/// The dyed card is a woven label: a seam runs just inside the edge, as if it had been sewn onto the page.
struct DyeCard: ViewModifier {
    var dye: Dye
    var padding: CGFloat
    @Environment(\.colorScheme) private var scheme

    func body(content: Content) -> some View {
        let shape = RoundedRectangle(cornerRadius: 26, style: .continuous)
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .environment(\.colorScheme, .dark)
            .environment(\.onCloth, true)
            .background {
                ZStack {
                    DyeField(dye: dye, deep: scheme == .dark)
                    LinearGradient(colors: [.white.opacity(scheme == .dark ? 0.1 : 0.07), .clear], startPoint: .top, endPoint: .center)
                }
                .clipShape(shape)
                .background(shape.fill(dye.glow).shadow(color: dye.glow.opacity(scheme == .dark ? 0.2 : 0.28), radius: 16, y: 8))
            }
            .overlay(shape.inset(by: 6).strokeBorder(.white.opacity(0.24), style: StrokeStyle(lineWidth: 1, lineCap: .round, dash: [6, 5])))
            .overlay(shape.strokeBorder(LinearGradient(colors: [.white.opacity(0.32), .white.opacity(0.05)], startPoint: .top, endPoint: .bottom), lineWidth: 0.75))
    }
}

extension EnvironmentValues {
    @Entry var onCloth = false
    @Entry var zoomSpace: Namespace.ID?
}

extension View {
    func card(padding: CGFloat = 16, tint: Tone? = nil) -> some View { modifier(CardStyle(padding: padding, tint: tint)) }
    func dyeCard(_ dye: Dye = .thread, padding: CGFloat = 22) -> some View { modifier(DyeCard(dye: dye, padding: padding)) }
}

/// A garment swing tag: the two left corners clipped, as cut from card.
struct TagShape: InsettableShape {
    var chamfer: CGFloat = 13
    var radius: CGFloat = 20
    var inset: CGFloat = 0

    func path(in rect: CGRect) -> Path {
        let r = rect.insetBy(dx: inset, dy: inset)
        var p = Path()
        p.move(to: CGPoint(x: r.minX + chamfer, y: r.minY))
        p.addLine(to: CGPoint(x: r.maxX - radius, y: r.minY))
        p.addArc(tangent1End: CGPoint(x: r.maxX, y: r.minY), tangent2End: CGPoint(x: r.maxX, y: r.minY + radius), radius: radius)
        p.addLine(to: CGPoint(x: r.maxX, y: r.maxY - radius))
        p.addArc(tangent1End: CGPoint(x: r.maxX, y: r.maxY), tangent2End: CGPoint(x: r.maxX - radius, y: r.maxY), radius: radius)
        p.addLine(to: CGPoint(x: r.minX + chamfer, y: r.maxY))
        p.addLine(to: CGPoint(x: r.minX, y: r.maxY - chamfer))
        p.addLine(to: CGPoint(x: r.minX, y: r.minY + chamfer))
        p.closeSubpath()
        return p
    }

    func inset(by amount: CGFloat) -> TagShape { TagShape(chamfer: chamfer, radius: radius, inset: inset + amount) }
}

/// Every order is a swing tag. The dyed stub says where it is in its life; a line of stitches joins it to the details.
/// The eyelet is where the section's thread passes through.
struct TagCard<Content: View>: View {
    var stage: Stage
    var alert: Tone?
    @ViewBuilder var content: Content
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        let shape = TagShape()
        content
            .padding(.leading, 58).padding(.trailing, 14).padding(.vertical, 12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background {
                ZStack(alignment: .leading) {
                    Surface(tint: alert?.color)
                    Rectangle().fill(alert?.gradient ?? stage.gradient).frame(width: 44)
                }
                .clipShape(shape)
            }
            .overlay(alignment: .leading) {
                HStack(spacing: 0) {
                    VStack(spacing: 0) {
                        Circle().fill(Ink.canvas).frame(width: 9, height: 9).overlay(Circle().strokeBorder(.white.opacity(0.75), lineWidth: 1.5)).padding(.top, 11)
                        Spacer(minLength: 6)
                        Image(systemName: alert == nil ? stage.symbol : "exclamationmark").font(.system(size: 15, weight: .bold)).foregroundStyle(.white)
                        Spacer(minLength: 14)
                    }
                    .frame(width: 44)
                    VStitch(colour: (alert?.color ?? stage.color).opacity(0.55)).padding(.vertical, 5).padding(.leading, 1)
                }
                .allowsHitTesting(false)
            }
            .hairline(shape, dark: scheme == .dark)
    }
}

private struct Across: Shape {
    func path(in rect: CGRect) -> Path {
        Path { $0.move(to: CGPoint(x: rect.minX, y: rect.midY)); $0.addLine(to: CGPoint(x: rect.maxX, y: rect.midY)) }
    }
}

private struct Down: Shape {
    func path(in rect: CGRect) -> Path {
        Path { $0.move(to: CGPoint(x: rect.midX, y: rect.minY)); $0.addLine(to: CGPoint(x: rect.midX, y: rect.maxY)) }
    }
}

/// A run of stitches going down the page.
struct VStitch: View {
    var colour: Color
    var width: CGFloat = 1.5

    var body: some View {
        Down().stroke(colour, style: StrokeStyle(lineWidth: width, lineCap: .round, dash: [5, 5]))
            .frame(width: width)
            .accessibilityHidden(true)
    }
}

/// A small square of colour holding one symbol, so a card can be read before its words are.
struct GlyphBadge: View {
    var symbol: String
    var tone: Tone = .info
    var size: CGFloat = 38

    var body: some View {
        Image(systemName: symbol)
            .font(.system(size: size * 0.44, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(tone.gradient, in: .rect(cornerRadius: size * 0.34, style: .continuous))
            .accessibilityHidden(true)
    }
}

struct DyeButton: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Ink.press, in: .capsule)
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

/// The signature: a line of stitches. Every journey in the app is drawn with it. Only a thread being sewn right now moves.
struct Stitches: View {
    var running = false
    var gradient = false
    var width: CGFloat = 2.5
    var colour: Color = Ink.line

    var body: some View {
        Group {
            if running {
                TimelineView(.animation(minimumInterval: 1 / 30)) { context in
                    line(phase: context.date.timeIntervalSinceReferenceDate * 22)
                }
            } else {
                line(phase: 0)
            }
        }
        .frame(height: max(width, 4))
        .accessibilityHidden(true)
    }

    /// The phase stays within one stitch. A dash is walked from its start, so a phase in the billions freezes the screen for a second a frame.
    private func line(phase: Double) -> some View {
        Across().stroke(gradient ? AnyShapeStyle(Ink.thread) : AnyShapeStyle(colour),
                        style: StrokeStyle(lineWidth: width, lineCap: .round, dash: [8, 7], dashPhase: -phase.truncatingRemainder(dividingBy: 15)))
    }
}

extension Color {
    init(hex: UInt32) { self.init(uiColor: UIColor(hex: hex)) }
}

struct Pill: View {
    var text: String
    var tone: Tone = .info

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .foregroundStyle(tone.color)
            .padding(.horizontal, 9)
            .padding(.vertical, 4)
            .background(tone.wash, in: .capsule)
    }
}

/// Two labelled numbers side by side, used wherever a decision shows its evidence.
struct Fact: View {
    var label: String
    var value: String
    var tone: Color = Ink.primary
    @Environment(\.onCloth) private var onCloth

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value).font(.title3.weight(.semibold)).monospacedDigit().foregroundStyle(onCloth ? .white : tone).minimumScaleFactor(0.7).lineLimit(1)
            Text(label).font(.caption).foregroundStyle(onCloth ? .white.opacity(0.82) : Ink.secondary).lineLimit(1).minimumScaleFactor(0.75)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

private struct Seams: Shape {
    func path(in rect: CGRect) -> Path {
        Path { path in
            for y in [rect.minY + 8, rect.maxY - 8] {
                path.move(to: CGPoint(x: rect.minX + 24, y: y))
                path.addLine(to: CGPoint(x: rect.maxX - 24, y: y))
            }
        }
    }
}

/// A slide, not a tap, for anything that goes out to another business. It cannot happen by accident,
/// and VoiceOver users get the same action as a plain button.
struct SlideToConfirm: View {
    var label: String
    var tint: Color = Ink.human
    var action: () -> Void

    @State private var offset: CGFloat = 0
    @State private var done = false
    private let knob: CGFloat = 54
    private let seam = StrokeStyle(lineWidth: 1.5, lineCap: .round, dash: [6, 5])

    var body: some View {
        GeometryReader { geometry in
            let travel = geometry.size.width - knob - 8
            let progress = travel > 0 ? min(1, offset / travel) : 0
            ZStack(alignment: .leading) {
                Capsule().fill(LinearGradient(colors: [tint.opacity(0.08), tint.opacity(0.2)], startPoint: .leading, endPoint: .trailing))
                Capsule().fill(tint.opacity(0.2)).frame(width: knob + 8 + offset)
                Seams().stroke(tint.opacity(0.28), style: seam)       // Two seams, sewn as the knob passes.
                Seams().stroke(tint, style: seam)
                    .mask(alignment: .leading) { Rectangle().frame(width: knob / 2 + offset) }
                Text(done ? "Done" : label)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(tint)
                    .frame(maxWidth: .infinity)
                    .padding(.leading, knob * 0.6)
                    .opacity(1 - progress * 0.9)
                Circle()
                    .fill(Tone.good.gradient)
                    .frame(width: knob, height: knob)
                    .overlay(Image(systemName: done ? "checkmark" : "chevron.right.2").font(.headline.weight(.bold)).foregroundStyle(.white).contentTransition(.symbolEffect(.replace)))
                    .padding(4)
                    .offset(x: offset)
                    .highPriorityGesture(DragGesture(minimumDistance: 2)
                        .onChanged { value in
                            guard !done else { return }
                            let next = max(0, min(travel, value.translation.width))
                            if Int(next / 22) != Int(offset / 22) { Haptics.stitch() }
                            if next >= travel, offset < travel { Haptics.tick() }
                            offset = next
                        }
                        .onEnded { _ in
                            guard !done else { return }
                            if offset >= travel * 0.9 {
                                offset = travel
                                done = true
                                Haptics.success()
                                action()
                            } else {
                                withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) { offset = 0 }
                            }
                        })
            }
        }
        .frame(height: 62)
        .accessibilityElement()
        .accessibilityLabel(label)
        .accessibilityAddTraits(.isButton)
        .accessibilityAction { done = true; action() }
    }
}

enum Haptics {
    private static let impact = UIImpactFeedbackGenerator(style: .light)
    private static let selection = UISelectionFeedbackGenerator()
    private static let notice = UINotificationFeedbackGenerator()

    static func tick() { impact.impactOccurred() }
    static func stitch() { selection.selectionChanged() }
    static func success() { notice.notificationOccurred(.success) }
    static func warning() { notice.notificationOccurred(.warning) }
}

enum Dates {
    private static let input: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    /// Formatters are slow to make and a calendar asks for hundreds, so each pattern gets one.
    private static var formatters: [String: DateFormatter] = [:]
    private static let lock = NSLock()
    private static let stamp = ISO8601DateFormatter()

    private static func formatter(_ pattern: String) -> DateFormatter {
        lock.lock()
        defer { lock.unlock() }
        if let found = formatters[pattern] { return found }
        let made = DateFormatter()
        made.locale = Locale(identifier: "en_GB")
        made.dateFormat = pattern
        formatters[pattern] = made
        return made
    }

    private static func format(_ text: String?, _ pattern: String) -> String {
        guard let text, let day = input.date(from: String(text.prefix(10))) else { return "n/a" }
        return formatter(pattern).string(from: day)
    }

    private static let calendar: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.firstWeekday = 2
        return c
    }()

    static func day(_ text: String?) -> Date? { text.flatMap { input.date(from: String($0.prefix(10))) } }
    static func key(_ day: Date) -> String { input.string(from: day) }
    static func add(_ days: Int, to day: Date) -> Date { calendar.date(byAdding: .day, value: days, to: day) ?? day }
    static func gap(_ from: Date, _ to: Date) -> Int { calendar.dateComponents([.day], from: from, to: to).day ?? 0 }
    static func isWeekend(_ day: Date) -> Bool { calendar.isDateInWeekend(day) }

    static func label(_ day: Date, _ pattern: String) -> String { formatter(pattern).string(from: day) }

    /// The days of a month in a Monday-first grid, with nil for the blanks before the 1st.
    static func grid(_ month: Date) -> [Date?] {
        guard let first = calendar.date(from: calendar.dateComponents([.year, .month], from: month)),
              let range = calendar.range(of: .day, in: .month, for: first) else { return [] }
        let blanks = (calendar.component(.weekday, from: first) + 5) % 7
        return Array(repeating: nil, count: blanks) + range.map { add($0 - 1, to: first) }
    }

    static func addMonths(_ months: Int, to day: Date) -> Date { calendar.date(byAdding: .month, value: months, to: day) ?? day }

    static func short(_ text: String?) -> String { format(text, "d MMM") }
    static func weekday(_ text: String?) -> String { format(text, "EEEE d MMMM") }

    static func time(_ text: String?) -> String {
        guard let text, let day = stamp.date(from: text) else { return "" }
        return day.formatted(date: .omitted, time: .shortened)
    }
}

func spareText(_ days: Int?) -> String {
    guard let days else { return "No date" }
    if days < 0 { return "\(-days) day\(days == -1 ? "" : "s") late" }
    return "\(days) day\(days == 1 ? "" : "s") to spare"
}

func money(_ value: Double?) -> String {
    guard let value else { return "n/a" }
    return value.formatted(.number.precision(.fractionLength(0)))
}

/// Chips that wrap onto a new line, so every fact stays on screen.
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        let spots = place(subviews, width: width)
        return CGSize(width: proposal.width ?? spots.map(\.maxX).max() ?? 0, height: spots.map(\.maxY).max() ?? 0)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        for (view, spot) in zip(subviews, place(subviews, width: bounds.width)) {
            view.place(at: CGPoint(x: bounds.minX + spot.minX, y: bounds.minY + spot.minY), proposal: ProposedViewSize(spot.size))
        }
    }

    private func place(_ subviews: Subviews, width: CGFloat) -> [CGRect] {
        var spots: [CGRect] = []
        var x: CGFloat = 0, y: CGFloat = 0, row: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > 0, x + size.width > width {
                x = 0
                y += row + spacing
                row = 0
            }
            spots.append(CGRect(origin: CGPoint(x: x, y: y), size: size))
            x += size.width + spacing
            row = max(row, size.height)
        }
        return spots
    }
}

private extension CGFloat {
    func clamped(to range: ClosedRange<CGFloat>) -> CGFloat { Swift.min(Swift.max(self, range.lowerBound), range.upperBound) }
}
