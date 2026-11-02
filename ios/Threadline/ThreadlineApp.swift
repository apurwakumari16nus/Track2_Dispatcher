import SwiftUI
import UserNotifications

/// Hands the phone's alert address to the desk, so a workshop's news can reach you with the app closed.
final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let hex = deviceToken.map { String(format: "%02x", $0) }.joined()
        Task { let _: Done? = try? await API.shared.post("/api/device", ["token": hex]) }
    }
}

@main
struct ThreadlineApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @State private var model = AppModel()
    @Environment(\.scenePhase) private var phase
    @AppStorage("appearance") private var appearance = "system"

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .fullScreenCover(isPresented: $model.showStory) { StoryView() }
                .preferredColorScheme(appearance == "dark" ? .dark : appearance == "light" ? .light : nil)
                .task {
                    if Probe.enabled { Probe.shared.start(model) }
                    if (try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])) == true {
                        UIApplication.shared.registerForRemoteNotifications()
                    }
                    await model.listen()
                }
                .onOpenURL { url in
                    if url.host() == "speak" { model.startSpeaking() }
                    if url.host() == "story" { model.showStory = true }
                }
                .onChange(of: phase) {
                    if phase == .background { model.holdForIsland() }
                    guard phase == .active else { return }
                    model.releaseIsland()
                    if Shared.defaults.bool(forKey: "openSpeak") {
                        Shared.defaults.set(false, forKey: "openSpeak")
                        model.startSpeaking()
                    }
                    Task { await model.refresh() }
                }
        }
    }
}
