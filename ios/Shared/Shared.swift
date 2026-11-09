import ActivityKit
import AppIntents
import Foundation

/// Settings and the small summary the widgets read. The app group is how the extension sees them.
enum Shared {
    static let group = "group.com.adityapandhari.threadline"
    static var defaults: UserDefaults { UserDefaults(suiteName: group) ?? .standard }

    /// A build for one test phone can carry the desk's address, so there is nothing to type. Normal builds leave these empty.
    private static func built(_ key: String) -> String? {
        (Bundle.main.object(forInfoDictionaryKey: key) as? String).flatMap { $0.isEmpty ? nil : $0 }
    }

    /// A Mac on this network, or the bare name of a public address, which is always https.
    private static func address(_ host: String) -> String {
        host.hasSuffix(".local") ? "http://\(host):8600" : "https://\(host)"
    }

    /// A build carrying a new address or token replaces what an older build left saved on the phone.
    private static func adopt() {
        let carried = (built("ThreadlineHost") ?? "") + "|" + (built("ThreadlineToken") ?? "")
        guard carried != "|", defaults.string(forKey: "carried") != carried else { return }
        defaults.set(carried, forKey: "carried")
        defaults.removeObject(forKey: "serverURL")
        defaults.removeObject(forKey: "token")
    }

    static var serverURL: String {
        get { adopt(); return defaults.string(forKey: "serverURL") ?? built("ThreadlineHost").map(address) ?? "http://127.0.0.1:8600" }
        set { defaults.set(newValue, forKey: "serverURL") }
    }
    static var isPublic: Bool { serverURL.hasPrefix("https://") }
    static var unreachable: String {
        isPublic ? "Cannot reach the desk. The Mac running it needs to be on." : "Cannot reach the desk. Your Mac and iPhone need to be on the same network."
    }
    static var token: String {
        get { adopt(); return defaults.string(forKey: "token").flatMap { $0.isEmpty ? nil : $0 } ?? built("ThreadlineToken") ?? "" }
        set { defaults.set(newValue, forKey: "token") }
    }
    static var name: String {
        get { defaults.string(forKey: "name") ?? "Dispatcher" }
        set { defaults.set(newValue, forKey: "name") }
    }
}

/// What the Lock Screen and widgets show.
struct Snapshot: Codable {
    var headline: String
    var top: String?
    var next: String?
    var count: Int
    var out: Int
    var updated: Date

    static let placeholder = Snapshot(headline: "All clear.", top: nil, next: nil, count: 0, out: 0, updated: .now)

    static func load() -> Snapshot {
        guard let data = Shared.defaults.data(forKey: "snapshot"),
              let value = try? JSONDecoder().decode(Snapshot.self, from: data) else { return .placeholder }
        return value
    }

    func save() {
        if let data = try? JSONEncoder().encode(self) { Shared.defaults.set(data, forKey: "snapshot") }
    }
}

/// A batch waiting on someone, live on the Lock Screen and in the Dynamic Island.
struct BatchActivity: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var status: String
        var detail: String
        var step: Int      // 0 sent, 1 accepted, 2 in production, 3 back
        var alert: Bool
    }

    var order: String
    var workshop: String
}

/// Opens the app ready to listen. Used by Siri, the Action button and Control Center.
struct OpenSpeakIntent: AppIntent {
    static let title: LocalizedStringResource = "Talk to Threadline"
    static let description = IntentDescription("Opens Threadline, ready to listen.")
    static let openAppWhenRun = true

    func perform() async throws -> some IntentResult & OpensIntent {
        Shared.defaults.set(true, forKey: "openSpeak")
        return .result(opensIntent: OpenURLIntent(URL(string: "threadline://speak")!))
    }
}
