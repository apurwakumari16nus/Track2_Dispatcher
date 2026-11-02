import ActivityKit
import Foundation
import Observation
import SwiftUI
import WidgetKit

struct ServerError: LocalizedError {
    var message: String
    var errorDescription: String? { message }
}

/// The one way to the desk. The app holds no business rules: every decision comes from the server.
struct API: Sendable {
    static let shared = API()

    /// Most calls answer in a fraction of a second, so a long wait only means the desk cannot be reached. Only reading needs longer.
    private func patience(_ path: String) -> TimeInterval {
        ["/api/speak", "/api/requests", "/api/roleplay/inbound", "/answer"].contains { path.contains($0) } ? 30 : 8
    }

    private func request(_ path: String, method: String = "GET", body: [String: Any]? = nil, timeout: TimeInterval? = nil) throws -> URLRequest {
        guard let url = URL(string: Shared.serverURL + path) else { throw ServerError(message: "Check the desk address in Settings.") }
        var request = URLRequest(url: url, timeoutInterval: timeout ?? patience(path))
        request.httpMethod = method
        if !Shared.token.isEmpty { request.setValue("Bearer \(Shared.token)", forHTTPHeaderField: "Authorization") }
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        return request
    }

    private func fetch(_ request: URLRequest) async throws -> Data {
        let data: Data, response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(for: request, delegate: Probe.enabled ? CallTimer() : nil)
        } catch {
            throw ServerError(message: Shared.unreachable)
        }
        if let http = response as? HTTPURLResponse, http.statusCode >= 400 {
            let detail = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
            throw ServerError(message: detail ?? "The desk could not do that.")
        }
        return data
    }

    func decode<T: Decodable>(_ data: Data, as type: T.Type = T.self) async throws -> T {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw ServerError(message: "The desk sent something this version of the app cannot read.")
        }
    }

    private func send<T: Decodable>(_ request: URLRequest, as type: T.Type = T.self) async throws -> T {
        try await decode(fetch(request))
    }

    /// The raw answer, so a desk with nothing new costs the phone no work at all.
    func data(_ path: String) async throws -> Data {
        try await fetch(request(path))
    }

    func get<T: Decodable>(_ path: String, as type: T.Type = T.self) async throws -> T {
        try await send(request(path))
    }

    func post<T: Decodable>(_ path: String, _ body: [String: Any] = [:], as type: T.Type = T.self) async throws -> T {
        try await send(request(path, method: "POST", body: ["by": Shared.name].merging(body) { $1 }))
    }

    func stream() async throws -> URLSession.AsyncBytes {
        let (bytes, _) = try await URLSession.shared.bytes(for: request("/api/stream", timeout: 15))   // The desk sends a heartbeat every 5 s.
        return bytes
    }

    /// A test build's timings, with no timing of its own.
    /// The Mac's reading of a clip. A short wait, because the phone's own words are already on screen.
    func hear(_ wav: Data, language: String = "auto") async throws -> Heard {
        var call = try request("/api/transcribe?language=\(language)", method: "POST", timeout: 6)
        call.setValue("audio/wav", forHTTPHeaderField: "Content-Type")
        call.httpBody = wav
        return try await send(call)
    }

    func language(_ wav: Data) async throws -> String {
        var call = try request("/api/language", method: "POST", timeout: 6)
        call.setValue("audio/wav", forHTTPHeaderField: "Content-Type")
        call.httpBody = wav
        let found: Found = try await send(call)
        return found.language
    }

    func report(_ entries: [[String: Any]]) async throws {
        _ = try await URLSession.shared.data(for: request("/api/perf", method: "POST", body: ["entries": entries]))
    }

    func encoded(_ text: String) -> String {
        text.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? text
    }
}

enum AppTab: Hashable { case today, work, messages, network, speak }

enum Route: Hashable {
    case incident(String), job(String), thread(String), workshop(String), letter(String), requests, trail, settings, voice, automations, rehearse
}

struct Banner: Identifiable, Equatable {
    let id = UUID()
    var title: String
    var text: String
    var tone: Tone
    var target: Target?
}

@Observable @MainActor
final class AppModel {
    var tab: AppTab = .today
    var paths: [AppTab: [Route]] = [:]
    var today: TodayData?
    var jobs: [Job] = []
    var threads: [ThreadSummary] = []
    var workshops: [Workshop] = []
    var requests: [WaitingRequest] = []
    var banner: Banner?
    var offline: String?
    var version = 0                      // Bumped on every change, so open screens reload themselves.
    @ObservationIgnored private var islandHold = UIBackgroundTaskIdentifier.invalid
    var showStory = false
    var freshSpeak = 0                   // Bumped when Speak must start clean: the Action button, Siri or a demo reset.
    var seedText: String?
    var workFilter: Stage?               // Tapping a stage anywhere opens Work showing only that stage.
    var composing = false
    let speech = SpeechEngine()
    let briefVoice = BriefVoice()
    private var activity: Activity<BatchActivity>?
    private var lastSnapshot: Data?
    private var refreshing: Task<Void, Never>?
    private var refreshAgain = false
    private var trackedKey: String?
    private var tokenWatch: Task<Void, Never>?

    /// Where you are in the app, for a test build's timings.
    var screenName: String {
        let top = (paths[tab] ?? []).last.map { String(String(describing: $0).prefix { $0 != "(" }) } ?? "root"
        return "\(tab)/\(top)"
    }

    /// How many orders sit at each point on the line, including requests nobody has decided yet.
    var stageCounts: [Stage: Int] {
        var counts = Dictionary(grouping: jobs, by: \.lane).mapValues(\.count)
        counts[.review, default: 0] += requests.count
        return counts
    }

    func showStage(_ stage: Stage) {
        Haptics.tick()
        paths[.work] = []
        workFilter = stage
        tab = .work
    }

    func path(_ tab: AppTab) -> Binding<[Route]> {
        Binding(get: { self.paths[tab] ?? [] }, set: { self.paths[tab] = $0 })
    }

    /// Opened by voice, so it goes straight to listening, whatever was left on screen.
    func startSpeaking() {
        tab = .speak
        freshSpeak += 1
    }

    func open(_ target: Target) {
        let route: Route? = switch target.type {
        case "incident": .incident(target.id)
        case "job": .job(target.id)
        case "thread": .thread(target.id)
        case "workshop": .workshop(target.id)
        case "letter": .letter(target.id)
        case "requests": .requests
        default: nil
        }
        guard let route else { return }
        var stack = tab == .speak ? (paths[.today] ?? []) : (paths[tab] ?? [])
        if tab == .speak { tab = .today }
        stack.append(route)
        paths[tab] = stack
    }

    /// Several things can ask at once, such as a tap and the live stream. They share one load, plus one more if anything came in during it.
    func refresh() async {
        if let refreshing {
            refreshAgain = true
            await refreshing.value
            return
        }
        let task = Task {
            repeat {
                refreshAgain = false
                await load()
            } while refreshAgain
        }
        refreshing = task
        await task.value
        refreshing = nil
    }

    private func load() async {
        do {
            let data = try await API.shared.data("/api/snapshot")
            if offline != nil { offline = nil }
            guard data != lastSnapshot else { return }
            let next: DeskSnapshot = try await API.shared.decode(data)
            lastSnapshot = data
            today = next.today
            jobs = next.jobs
            threads = next.threads
            requests = next.requests
            workshops = next.today.network
            version += 1
            let upcoming = next.today.comingBack.first.map { "Next back: \($0.order), \(Dates.short($0.back))" }
            Snapshot(headline: next.today.headline, top: next.today.attention.first?.title, next: upcoming, count: next.today.attention.count, out: next.today.out, updated: .now).save()
            WidgetCenter.shared.reloadAllTimelines()
            updateActivity()
        } catch {
            offline = error.localizedDescription
        }
    }

    /// Stays connected, so a reply in Telegram appears on the phone as it arrives. The banner goes up first and the screens catch up behind it.
    /// A public tunnel holds a live stream back, so over one the phone asks every few seconds instead.
    func listen() async {
        while !Task.isCancelled {
            if Shared.isPublic {
                await refresh()
                try? await Task.sleep(for: .seconds(4))
                continue
            }
            do {
                var event = ""
                for try await line in try await API.shared.stream().lines {
                    if line.hasPrefix("event: ") {
                        event = String(line.dropFirst(7))
                    } else if line.hasPrefix("data: "), event == "change" {
                        announce(String(line.dropFirst(6)))
                        Task { await refresh() }
                    } else if line.hasPrefix("data: "), event == "ready" {
                        Task { await refresh() }
                    }
                }
            } catch {
                offline = Shared.unreachable
            }
            try? await Task.sleep(for: .seconds(2))
        }
    }

    private var lastAnnounced = ""

    private func announce(_ payload: String) {
        guard payload != lastAnnounced, payload != "{}", let data = payload.data(using: .utf8),
              let item = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let title = item["title"] as? String, let text = item["text"] as? String else { return }
        lastAnnounced = payload
        let incident = item["kind"] as? String == "incident"
        let target = (incident ? (item["id"] as? String).map { Target(type: "incident", id: $0) } : (item["party"] as? String).map { Target(type: "thread", id: $0) })
        withAnimation(.spring(response: 0.45, dampingFraction: 0.82)) {
            banner = Banner(title: title, text: text, tone: incident ? .risk : .info, target: target)
        }
        incident ? Haptics.warning() : Haptics.tick()
        Task {
            try? await Task.sleep(for: .seconds(5))
            withAnimation { banner = nil }
        }
    }

    // Live Activity ----------------------------------------------------------

    func track(_ job: Job) {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { return }
        let state = BatchActivity.ContentState(status: "Waiting for \(job.workshop)", detail: "\(job.goods), back \(Dates.short(job.back))", step: 0, alert: false)
        let attributes = BatchActivity(order: job.order, workshop: job.workshop)
        let content = ActivityContent(state: state, staleDate: nil)
        activity = (try? Activity.request(attributes: attributes, content: content, pushType: .token)) ?? (try? Activity.request(attributes: attributes, content: content, pushType: nil))
        trackedKey = job.key
        sendIslandToken()
    }

    /// The desk needs this to move the Island once iOS has stopped the app. Apple can change it at any time, so every new one is sent.
    private func sendIslandToken() {
        guard let activity, let trackedKey else { return }
        tokenWatch?.cancel()
        tokenWatch = Task {
            for await token in activity.pushTokenUpdates {
                let hex = token.map { String(format: "%02x", $0) }.joined()
                let _: Done? = try? await API.shared.post("/api/island", ["key": trackedKey, "token": hex])
            }
        }
    }

    /// iOS gives an app about 30 seconds after you leave it. Held while a batch is on the Island, so a reply that comes straight after still moves it.
    func holdForIsland() {
        guard activity != nil, islandHold == .invalid else { return }
        islandHold = UIApplication.shared.beginBackgroundTask(withName: "island") { [weak self] in
            MainActor.assumeIsolated { self?.releaseIsland() }
        }
    }

    func releaseIsland() {
        guard islandHold != .invalid else { return }
        UIApplication.shared.endBackgroundTask(islandHold)
        islandHold = .invalid
    }

    private func updateActivity() {
        if activity == nil, let running = Activity<BatchActivity>.activities.first {     // A restart must not leave one stranded.
            activity = running
            trackedKey = jobs.first { $0.order == running.attributes.order && $0.workshop == running.attributes.workshop }?.key
            sendIslandToken()
        }
        guard let activity, let trackedKey, let job = jobs.first(where: { $0.key == trackedKey }), let island = job.island else { return }
        let state = BatchActivity.ContentState(status: island.status, detail: island.detail, step: island.step, alert: island.alert)
        let done = job.stage == "received"
        if done {
            self.activity = nil
            self.trackedKey = nil
        }
        Task {
            if done {
                await activity.end(.init(state: state, staleDate: nil), dismissalPolicy: .after(.now + 600))
            } else {
                await activity.update(.init(state: state, staleDate: nil))
            }
        }
    }
}
