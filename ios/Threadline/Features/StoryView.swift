import SwiftUI

/// The project's own story, shown in the app instead of slides. The words and numbers come from eval/build_story.py,
/// which reads them from the evaluation results, so nothing here is typed by hand.
struct Story: Decodable {
    var pages: [StoryPage]

    static let bundled: Story = {
        guard let url = Bundle.main.url(forResource: "story", withExtension: "json"), let data = try? Data(contentsOf: url),
              let story = try? JSONDecoder().decode(Story.self, from: data) else { return Story(pages: []) }
        return story
    }()
}

struct StoryPage: Decodable, Identifiable {
    var id: String
    var eyebrow: String
    var title: String
    var lead: String?
    var blocks: [StoryBlock]
}

struct StoryBlock: Decodable {
    var heading: String?
    var note: String?
    var bars: [StoryBar]?
    var facts: [StoryFact]?
    var points: [StoryPoint]?
}

struct StoryBar: Decodable, Identifiable {
    var label: String
    var value: Double
    var unit: String
    var ours: Bool
    var id: String { label }
}

struct StoryFact: Decodable, Identifiable {
    var value: String
    var label: String
    var id: String { label }
}

struct StoryPoint: Decodable, Identifiable {
    var title: String
    var detail: String
    var id: String { title }
}

struct StoryView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var page = 0
    private let pages = Story.bundled.pages

    var body: some View {
        ZStack(alignment: .topTrailing) {
            Backdrop()
            TabView(selection: $page) {
                ForEach(Array(pages.enumerated()), id: \.element.id) { index, item in
                    StoryPageView(page: item).tag(index)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .always))
            .indexViewStyle(.page(backgroundDisplayMode: .always))
            Button { dismiss() } label: {
                Image(systemName: "xmark").font(.subheadline.weight(.bold)).foregroundStyle(Ink.secondary).frame(width: 40, height: 40)
            }
            .accessibilityLabel("Close")
            .padding(.trailing, 12)
        }
    }
}

private struct StoryPageView: View {
    var page: StoryPage

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(page.eyebrow).font(.label).foregroundStyle(.white.opacity(0.85))
                    Text(page.title).font(.hero(32)).foregroundStyle(.white).fixedSize(horizontal: false, vertical: true)
                    if let lead = page.lead { Text(lead).font(.subheadline).foregroundStyle(.white.opacity(0.86)).fixedSize(horizontal: false, vertical: true) }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .dyeCard(page.id == "limits" ? .alarm : .thread)
                ForEach(Array(page.blocks.enumerated()), id: \.offset) { _, block in
                    VStack(alignment: .leading, spacing: 12) {
                        if let heading = block.heading { Text(heading).font(.headline).foregroundStyle(Ink.primary) }
                        if let bars = block.bars { StoryBars(bars: bars) }
                        if let facts = block.facts { StoryFacts(facts: facts) }
                        if let points = block.points {
                            ForEach(points) { point in
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(point.title).font(.subheadline.weight(.semibold)).foregroundStyle(Ink.primary)
                                    Text(point.detail).font(.footnote).foregroundStyle(Ink.secondary).fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        }
                        if let note = block.note { Text(note).font(.footnote).foregroundStyle(Ink.secondary).fixedSize(horizontal: false, vertical: true) }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .card(padding: 14)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 56)
            .padding(.bottom, 52)
        }
    }
}

private struct StoryBars: View {
    var bars: [StoryBar]

    var body: some View {
        let top = max(bars.map(\.value).max() ?? 1, 1)
        VStack(spacing: 10) {
            ForEach(bars) { bar in
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(bar.label).font(.subheadline.weight(bar.ours ? .semibold : .regular)).foregroundStyle(Ink.primary)
                        Spacer()
                        Text("\(bar.value.formatted(.number.precision(.fractionLength(1))))\(bar.unit)").font(.subheadline.weight(.semibold).monospacedDigit())
                            .foregroundStyle(bar.ours ? Ink.teal : Ink.secondary)
                    }
                    GeometryReader { space in
                        Capsule().fill(bar.ours ? AnyShapeStyle(Ink.thread) : AnyShapeStyle(Ink.tertiary.opacity(0.5)))
                            .frame(width: max(8, space.size.width * bar.value / top), height: 9)
                    }
                    .frame(height: 9)
                }
            }
        }
    }
}

private struct StoryFacts: View {
    var facts: [StoryFact]

    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible(), alignment: .topLeading), GridItem(.flexible(), alignment: .topLeading)], alignment: .leading, spacing: 14) {
            ForEach(facts) { fact in
                VStack(alignment: .leading, spacing: 2) {
                    Text(fact.value).font(.hero(24)).foregroundStyle(Ink.primary)
                    Text(fact.label).font(.caption).foregroundStyle(Ink.secondary).fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }
}
