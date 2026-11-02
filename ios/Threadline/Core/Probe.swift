import QuartzCore
import SwiftUI

/// A test build's stopwatch: how smooth each screen really was on this iPhone, and how long each desk call took.
/// It is off unless the build turns it on, and what it finds goes to the desk, so slowness can be seen rather than guessed.
@MainActor
final class Probe: NSObject {
    static let shared = Probe()
    nonisolated static let enabled = (Bundle.main.object(forInfoDictionaryKey: "ThreadlineProbe") as? String) == "1"

    private weak var model: AppModel?
    private var link: CADisplayLink?
    private var last: CFTimeInterval = 0
    private var windowStart: CFTimeInterval = 0
    private var frames = 0
    private var hitches = 0
    private var lost: Double = 0
    private var worst: Double = 0
    private var fps = 0
    private var calls: [[String: Any]] = []
    private var marks: [[String: Any]] = []
    private var pending: [[String: Any]] = []

    func start(_ model: AppModel) {
        guard link == nil else { return }
        self.model = model
        let link = CADisplayLink(target: self, selector: #selector(tick))
        link.add(to: .main, forMode: .common)
        self.link = link
    }

    @objc private func tick(_ link: CADisplayLink) {
        let now = link.timestamp
        defer { last = now }
        guard last > 0, now - last < 5 else {       // The first frame, or back from the background.
            windowStart = now
            clear()
            return
        }
        let gap = now - last
        let expected = max(link.targetTimestamp - now, 1.0 / 120)
        fps = Int((1 / expected).rounded())
        frames += 1
        if gap > expected * 1.5 {
            hitches += 1
            lost += gap - expected
            worst = max(worst, gap)
        }
        if now - windowStart >= 3 {
            finishWindow(seconds: now - windowStart)
            windowStart = now
        }
    }

    private func clear() {
        (frames, hitches, lost, worst) = (0, 0, 0, 0)
        calls = []
        marks = []
    }

    private func finishWindow(seconds: Double) {
        guard let model, hitches > 0 || !calls.isEmpty || !marks.isEmpty else { return clear() }
        pending.append(["screen": model.screenName, "seconds": seconds, "frames": frames, "hitches": hitches, "lost_ms": Int(lost * 1000), "worst_ms": Int(worst * 1000),
                        "fps": fps, "low_power": ProcessInfo.processInfo.isLowPowerModeEnabled, "thermal": ProcessInfo.processInfo.thermalState.rawValue,
                        "calls": calls, "marks": marks])
        clear()
        let batch = pending
        Task {
            do {
                try await API.shared.report(batch)
                pending.removeFirst(min(batch.count, pending.count))
            } catch {
                pending = Array(pending.suffix(60))     // Kept until the desk is back: those are the moments that matter most.
            }
        }
    }

    func add(_ call: [String: Any]) {
        calls.append(call)
    }

    func mark(_ name: String, since start: Date) {
        guard Self.enabled else { return }
        marks.append(["name": name, "ms": Int(Date().timeIntervalSince(start) * 1000)])
    }
}

/// How long one desk call took, and where the time went.
final class CallTimer: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask, didFinishCollecting metrics: URLSessionTaskMetrics) {
        guard let timing = metrics.transactionMetrics.last else { return }
        func span(_ from: Date?, _ to: Date?) -> Int {
            guard let from, let to else { return 0 }
            return Int(to.timeIntervalSince(from) * 1000)
        }
        let path = task.originalRequest?.url?.path ?? ""
        let status = (task.response as? HTTPURLResponse)?.statusCode ?? 0
        let total = Int(metrics.taskInterval.duration * 1000)
        let lookup = span(timing.domainLookupStartDate, timing.domainLookupEndDate)
        let connect = span(timing.connectStartDate, timing.connectEndDate)
        let wait = span(timing.requestEndDate, timing.responseStartDate)
        let reused = timing.isReusedConnection
        Task { @MainActor in
            Probe.shared.add(["path": path, "ms": total, "status": status, "lookup": lookup, "connect": connect, "wait": wait, "reused": reused])
        }
    }
}
