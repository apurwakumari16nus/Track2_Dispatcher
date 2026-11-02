import SwiftUI

struct NetworkView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        NavigationStack(path: model.path(.network)) {
            ScrollView {
                if let day = Dates.day(model.today?.today) {
                    Loom(today: day, workshops: model.workshops, jobs: model.jobs)
                        .padding(.horizontal, 16)
                        .padding(.bottom, 24)
                }
            }
            .background(Backdrop())
            .navigationTitle("Network")
            .refreshable { await model.refresh() }
            .destinations()
        }
    }
}

/// Every workshop as a thread across the next two weeks. Each stitch is a batch, in the order it will be sewn,
/// ending on the day it is booked back. Who has room, who is stretched and what lands when, in one picture.
struct Loom: View {
    var today: Date
    var workshops: [Workshop]
    var jobs: [Job]
    let span = 14

    private var ordered: [Workshop] { workshops.filter(\.isOpen) + workshops.filter { !$0.isOpen } }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            axis
            ForEach(ordered) { workshop in
                LoomThread(workshop: workshop, today: today, span: span, jobs: jobs.filter { $0.workshopId == workshop.id && $0.stage != "received" })
            }
            Text("Each stitch is a batch, ending the day it is due back.").font(.caption).foregroundStyle(Ink.secondary).padding(.top, 2)
            StageLegend()
        }
        .card(padding: 14)
    }

    private var axis: some View {
        HStack(spacing: 0) {
            ForEach(0 ..< span, id: \.self) { index in
                let day = Dates.add(index, to: today)
                VStack(spacing: 1) {
                    Text(Dates.label(day, "EEEEE")).font(.system(size: 9, weight: .medium)).foregroundStyle(Ink.tertiary)
                    Text(Dates.label(day, "d")).font(.system(size: 11, weight: index == 0 ? .bold : .medium)).monospacedDigit()
                        .foregroundStyle(index == 0 ? Ink.cobalt : Dates.isWeekend(day) ? Ink.tertiary : Ink.secondary)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .accessibilityHidden(true)
    }
}

private struct LoomThread: View {
    var workshop: Workshop
    var today: Date
    var span: Int
    var jobs: [Job]

    private struct Stitch: Identifiable {
        var job: Job
        var from: Double
        var to: Double
        var id: String { job.key }
    }

    /// Batches are sewn one after another, so each stitch starts where the last one ended.
    private var stitches: [Stitch] {
        var cursor = 0.0
        return jobs.compactMap { job in Dates.day(job.back).map { (job, $0) } }.sorted { $0.1 < $1.1 }.map { job, back in
            let end = min(Double(span), max(cursor + 0.7, Double(Dates.gap(today, back) + 1)))
            defer { cursor = end }
            return Stitch(job: job, from: cursor, to: end)
        }
    }

    private var state: (text: String, colour: Color) {
        if !workshop.isOpen {
            return (workshop.notices.last?.until.map { "Closed until \(Dates.short($0))" } ?? "Suspended", Ink.coral)
        }
        if workshop.reported != nil { return ("Reported a change", Ink.amber) }
        if workshop.queueDays <= 0 { return ("Free now", Ink.teal) }
        if workshop.queueDays < 1 { return ("Under a day booked", Ink.teal) }
        let days = Int(workshop.queueDays.rounded())
        return ("\(days) day\(days == 1 ? "" : "s") booked", workshop.load > 0.75 ? Ink.amber : Ink.secondary)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            NavigationLink(value: Route.workshop(workshop.id)) {
                HStack {
                    Text(workshop.name).font(.subheadline.weight(.semibold)).foregroundStyle(workshop.isOpen ? Ink.primary : Ink.secondary)
                    Spacer()
                    Text(state.text).font(.caption.weight(.medium)).foregroundStyle(state.colour)
                }
                .contentShape(.rect)
            }
            .buttonStyle(.plain)
            GeometryReader { geometry in
                let day = geometry.size.width / CGFloat(span)
                ZStack(alignment: .leading) {
                    Canvas { canvas, size in
                        for index in 0 ..< span where Dates.isWeekend(Dates.add(index, to: today)) {
                            canvas.fill(Path(roundedRect: CGRect(x: CGFloat(index) * day, y: 0, width: day, height: size.height), cornerRadius: 3), with: .color(Ink.well.opacity(0.6)))
                        }
                        var line = Path()
                        line.move(to: CGPoint(x: 0, y: size.height / 2))
                        line.addLine(to: CGPoint(x: size.width, y: size.height / 2))
                        canvas.stroke(line, with: .color(workshop.isOpen ? Ink.line : Ink.coral.opacity(0.45)), style: StrokeStyle(lineWidth: 2, lineCap: .round, dash: [5, 6]))
                    }
                    ForEach(stitches) { stitch in
                        let width = CGFloat(stitch.to - stitch.from) * day - 2
                        NavigationLink(value: Route.job(stitch.job.key)) {
                            ZStack {
                                RoundedRectangle(cornerRadius: 7, style: .continuous).fill(stitch.job.fill)
                                if width >= 28 {
                                    Text(width >= 54 ? stitch.job.order : String(stitch.job.order.suffix(3)))
                                        .font(.system(size: 10, weight: .semibold)).monospacedDigit().foregroundStyle(.white).lineLimit(1)
                                }
                            }
                        }
                        .buttonStyle(.plain)
                        .frame(width: width, height: 20)
                        .offset(x: CGFloat(stitch.from) * day + 1)
                        .accessibilityLabel("\(stitch.job.order), \(stitch.job.stageLabel), back \(Dates.short(stitch.job.back))")
                    }
                }
            }
            .frame(height: 20)
        }
    }
}

struct WorkshopView: View {
    @Environment(AppModel.self) private var model
    var id: String
    @State private var workshop: Workshop?

    var body: some View {
        ScrollView {
            if let workshop {
                VStack(alignment: .leading, spacing: 14) {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(workshop.isOpen ? "Working" : "Closed").font(.label).foregroundStyle(.white.opacity(0.85))
                        Text(workshop.name).font(.hero(36)).foregroundStyle(Ink.primary)
                        Text(workshop.notes.prefix(1).uppercased() + workshop.notes.dropFirst() + ".").font(.subheadline).foregroundStyle(.white.opacity(0.82))
                        ForEach(workshop.notices, id: \.self) { notice in
                            Text([notice.label, notice.reason].compactMap { $0 }.joined(separator: ", ")).font(.footnote).foregroundStyle(Color(hex: 0xFFD98A))
                        }
                        if let reported = workshop.reported { Text(reported + ". Waiting for your approval.").font(.footnote).foregroundStyle(Color(hex: 0xFFD98A)) }
                        HStack(alignment: .top) {
                            Fact(label: "Queue", value: "\(workshop.queueDays.formatted(.number.precision(.fractionLength(1)))) d")
                            Fact(label: "A day", value: "\(workshop.capacity)")
                            Fact(label: "Per piece", value: workshop.cost.formatted())
                            Fact(label: "Defects", value: workshop.defectRate.formatted(.percent.precision(.fractionLength(0))))
                        }
                        if let completed = workshop.completed, completed > 0 {
                            Text("\(completed) completed and not back yet. \(completed == 1 ? "It no longer counts" : "They no longer count") in the queue.")
                                .font(.footnote).foregroundStyle(.white.opacity(0.82))
                        }
                    }
                    .dyeCard(workshop.isOpen ? .thread : .alarm)
                    Button { model.open(Target(type: "thread", id: workshop.id)) } label: {
                        Text("Message \(workshop.name)")
                    }
                    .buttonStyle(DyeButton())
                    if let jobs = workshop.jobs, !jobs.isEmpty {
                        Text("Open batches").font(.headline).foregroundStyle(Ink.primary).padding(.top, 4)
                        ForEach(jobs) { job in
                            NavigationLink(value: Route.job(job.key)) { JobTag(job: job) }.buttonStyle(.plain)
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
        }
        .background(Backdrop())
        .navigationBarTitleDisplayMode(.inline)
        .task(id: model.version) { workshop = try? await API.shared.get("/api/workshops/\(id)") }
    }
}
