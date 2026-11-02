import SwiftUI

/// The dispatcher's calendar: what comes back on which day, drawn as stitches under the date.
/// Two weeks at a glance, or the whole month.
struct ThreadCalendar: View {
    @Environment(AppModel.self) private var model
    var today: Date

    var body: some View {
        CalendarDays(today: today, byDay: Dictionary(grouping: model.jobs.filter { $0.stage != "received" && $0.back != nil }) { String(($0.back ?? "").prefix(10)) })
    }
}

private struct CalendarDays: View {
    var today: Date
    var byDay: [String: [Job]]     // Worked out once for all the days, rather than once per day.
    @State private var picked: Date?
    @State private var wholeMonth = false
    @State private var month: Date?

    private var selected: Date {
        picked ?? byDay.keys.sorted().compactMap(Dates.day).first { $0 >= today } ?? today
    }

    private var strip: [Date] {
        let last = byDay.keys.compactMap(Dates.day).max() ?? today
        return (0 ... min(41, max(13, Dates.gap(today, last)))).map { Dates.add($0, to: today) }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(wholeMonth ? Dates.label(month ?? today, "MMMM yyyy") : "Coming back").font(.headline).foregroundStyle(Ink.primary).contentTransition(.opacity)
                Spacer()
                if wholeMonth {
                    Button { step(-1) } label: { Image(systemName: "chevron.left") }.accessibilityLabel("Previous month")
                    Button { step(1) } label: { Image(systemName: "chevron.right") }.accessibilityLabel("Next month").padding(.horizontal, 6)
                }
                Button(wholeMonth ? "Two weeks" : "Month", systemImage: "calendar") {
                    withAnimation(.smooth) {
                        wholeMonth.toggle()
                        month = selected
                    }
                }
                .font(.subheadline.weight(.medium))
            }
            .font(.footnote.weight(.semibold))
            if wholeMonth { monthGrid } else { fortnight }
            detail
        }
    }

    private func step(_ months: Int) {
        withAnimation(.smooth) { month = Dates.addMonths(months, to: month ?? today) }
    }

    private func tile(_ day: Date, compact: Bool) -> some View {
        Button {
            Haptics.tick()
            withAnimation(.smooth(duration: 0.25)) { picked = day }
        } label: {
            DayTile(day: day, jobs: byDay[Dates.key(day)] ?? [], chosen: Dates.key(day) == Dates.key(selected), isToday: Dates.key(day) == Dates.key(today), compact: compact)
        }
        .buttonStyle(.plain)
    }

    private var fortnight: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(strip, id: \.self) { day in tile(day, compact: false) }
            }
            .padding(.vertical, 2)
        }
        .scrollClipDisabled()
        .transition(.opacity)
    }

    private var monthGrid: some View {
        VStack(spacing: 6) {
            HStack(spacing: 0) {
                ForEach(["M", "T", "W", "T", "F", "S", "S"].indices, id: \.self) { index in
                    Text(["M", "T", "W", "T", "F", "S", "S"][index]).font(.caption2.weight(.semibold)).foregroundStyle(Ink.tertiary).frame(maxWidth: .infinity)
                }
            }
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 5), count: 7), spacing: 5) {
                ForEach(Array(Dates.grid(month ?? today).enumerated()), id: \.offset) { _, day in
                    if let day { tile(day, compact: true) } else { Color.clear.frame(height: 46) }
                }
            }
        }
        .card(padding: 10)
        .transition(.opacity)
    }

    private var detail: some View {
        let jobs = (byDay[Dates.key(selected)] ?? []).sorted { $0.order < $1.order }
        return VStack(alignment: .leading, spacing: 4) {
            Text(Dates.label(selected, "EEEE d MMMM")).font(.subheadline.weight(.semibold)).foregroundStyle(Ink.primary)
            if jobs.isEmpty {
                Text("Nothing is booked back on this day.").font(.subheadline).foregroundStyle(Ink.secondary)
            }
            ForEach(jobs) { job in
                NavigationLink(value: Route.job(job.key)) {
                    HStack(spacing: 12) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(job.order), \(job.workshop)").font(.subheadline.weight(.medium)).foregroundStyle(Ink.primary).lineLimit(1)
                            Text("\(job.goods), \(job.stageLabel.lowercased())").font(.footnote).foregroundStyle(Ink.secondary).lineLimit(1)
                        }
                        Spacer()
                        StepDots(step: job.step)
                    }
                    .padding(.vertical, 7)
                    .contentShape(.rect)
                }
                .buttonStyle(.plain)
            }
        }
        .card(padding: 14)
        .id(Dates.key(selected))
        .transition(.opacity)
    }
}

private struct DayTile: View {
    var day: Date
    var jobs: [Job]
    var chosen: Bool
    var isToday: Bool
    var compact: Bool

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: compact ? 12 : 16, style: .continuous)
        VStack(spacing: compact ? 3 : 5) {
            if !compact {
                Text(Dates.label(day, "EEE")).font(.caption2.weight(.medium)).foregroundStyle(chosen ? .white.opacity(0.85) : Ink.secondary)
            }
            Text(Dates.label(day, "d")).font(compact ? .subheadline.weight(.semibold) : .title3.weight(.semibold)).monospacedDigit()
                .foregroundStyle(chosen ? .white : Dates.isWeekend(day) ? Ink.secondary : Ink.primary)
            HStack(spacing: 2) {
                ForEach(jobs.prefix(3)) { job in
                    Capsule().fill(chosen ? AnyShapeStyle(.white) : job.fill).frame(width: compact ? 7 : 9, height: 3)
                }
            }
            .frame(height: 3)
        }
        .frame(width: compact ? nil : 50, height: compact ? 46 : 76)
        .frame(maxWidth: compact ? .infinity : nil)
        .background {
            if chosen {
                shape.fill(Ink.chosen)
            } else if !compact {
                Surface().clipShape(shape)
            }
        }
        .overlay {
            if isToday, !chosen { shape.strokeBorder(Ink.cobalt, lineWidth: 1.25) } else if !compact, !chosen { shape.strokeBorder(Ink.line, lineWidth: 0.75) }
        }
        .accessibilityElement()
        .accessibilityLabel("\(Dates.label(day, "EEEE d MMMM"))\(isToday ? ", today" : ""), \(jobs.count) back")
        .accessibilityAddTraits(chosen ? .isSelected : [])
    }
}
