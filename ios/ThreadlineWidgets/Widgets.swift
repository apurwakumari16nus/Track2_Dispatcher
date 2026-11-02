import ActivityKit
import AppIntents
import SwiftUI
import WidgetKit

private let cobalt = Color(red: 0.34, green: 0.47, blue: 0.95)
private let coral = Color(red: 0.92, green: 0.40, blue: 0.37)
private let cloth = LinearGradient(colors: [Color(red: 0.06, green: 0.11, blue: 0.19), Color(red: 0.14, green: 0.26, blue: 0.70), Color(red: 0.10, green: 0.60, blue: 0.62)], startPoint: .topLeading, endPoint: .bottomTrailing)

/// The same stage colours as the app, and the same order.
private let stageColours = [Color(red: 0.66, green: 0.55, blue: 0.98), Color(red: 0.49, green: 0.60, blue: 0.98), Color(red: 0.23, green: 0.81, blue: 0.85),
                            Color(red: 0.17, green: 0.82, blue: 0.71), Color(red: 0.24, green: 0.77, blue: 0.51)]

private struct Progress: View {
    var step: Int

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0 ..< 5, id: \.self) { index in
                Capsule().fill(index <= step ? stageColours[index] : .white.opacity(0.18)).frame(height: 4)
            }
        }
    }
}

/// The same symbol and colour the stage has everywhere else in the app. Warm means a problem.
private struct StageMark: View {
    var state: BatchActivity.ContentState

    var body: some View {
        let step = min(4, max(0, state.step))
        Image(systemName: state.alert ? "exclamationmark.triangle.fill" : ["paperplane.fill", "hand.thumbsup.fill", "scissors", "shippingbox.fill", "checkmark"][step])
            .foregroundStyle(state.alert ? Color.orange : stageColours[step])
    }
}

struct BatchLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: BatchActivity.self) { context in
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(context.attributes.order).font(.headline)
                    Spacer()
                    Text(context.state.status).font(.subheadline.weight(.semibold)).foregroundStyle(context.state.alert ? coral : .primary)
                }
                Text(context.state.detail).font(.footnote).foregroundStyle(.secondary)
                Progress(step: context.state.step)
            }
            .padding(16)
            .environment(\.colorScheme, .dark)
            .activityBackgroundTint(Color(red: 0.08, green: 0.13, blue: 0.24))
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Text(context.attributes.order).font(.headline).padding(.leading, 6)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(context.attributes.workshop).font(.subheadline).foregroundStyle(.secondary).padding(.trailing, 6)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(context.state.status).font(.subheadline.weight(.semibold)).foregroundStyle(context.state.alert ? coral : .white)
                        Progress(step: context.state.step)
                    }
                    .padding(.horizontal, 6)
                }
            } compactLeading: {
                StageMark(state: context.state)
            } compactTrailing: {
                Text(["Waiting", "Accepted", "Sewing", "Completed", "Back"][min(4, max(0, context.state.step))]).font(.caption2.weight(.semibold)).foregroundStyle(context.state.alert ? coral : stageColours[min(4, max(0, context.state.step))])
            } minimal: {
                StageMark(state: context.state)
            }
        }
    }
}

struct SnapshotEntry: TimelineEntry {
    var date: Date
    var snapshot: Snapshot
}

struct SnapshotProvider: TimelineProvider {
    func placeholder(in context: Context) -> SnapshotEntry { SnapshotEntry(date: .now, snapshot: .placeholder) }
    func getSnapshot(in context: Context, completion: @escaping (SnapshotEntry) -> Void) { completion(SnapshotEntry(date: .now, snapshot: .load())) }
    func getTimeline(in context: Context, completion: @escaping (Timeline<SnapshotEntry>) -> Void) {
        completion(Timeline(entries: [SnapshotEntry(date: .now, snapshot: .load())], policy: .after(.now.addingTimeInterval(1800))))
    }
}

private struct TodayWidgetView: View {
    @Environment(\.widgetFamily) private var family
    var snapshot: Snapshot

    var body: some View {
        let onCloth = family != .accessoryRectangular
        VStack(alignment: .leading, spacing: 4) {
            Text(snapshot.headline).font(.system(.title3, design: .serif, weight: .medium))
            if let top = snapshot.top {
                Text(top).font(.footnote).lineLimit(family == .systemSmall ? 3 : 2).opacity(0.85)
            }
            Spacer(minLength: 0)
            Text(snapshot.next ?? "\(snapshot.out) batches out").font(.caption2).opacity(0.8)
        }
        .foregroundStyle(onCloth ? AnyShapeStyle(.white) : AnyShapeStyle(.primary))
        .containerBackground(for: .widget) {
            if onCloth { cloth } else { Color.clear }
        }
    }
}

struct TodayWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "today", provider: SnapshotProvider()) { entry in
            TodayWidgetView(snapshot: entry.snapshot)
        }
        .configurationDisplayName("Today")
        .description("What needs you, at a glance.")
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryRectangular])
    }
}

struct TalkControl: ControlWidget {
    var body: some ControlWidgetConfiguration {
        StaticControlConfiguration(kind: "talk") {
            ControlWidgetButton(action: OpenSpeakIntent()) {
                Label("Talk to Threadline", systemImage: "waveform")
            }
        }
        .displayName("Talk to Threadline")
    }
}

@main
struct ThreadlineWidgets: WidgetBundle {
    var body: some Widget {
        BatchLiveActivity()
        TodayWidget()
        TalkControl()
    }
}
