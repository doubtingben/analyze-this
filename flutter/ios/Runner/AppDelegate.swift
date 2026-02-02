import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    let controller : FlutterViewController = window?.rootViewController as! FlutterViewController
    let shareChannel = FlutterMethodChannel(name: "com.analyzethis/share",
                                              binaryMessenger: controller.binaryMessenger)
    shareChannel.setMethodCallHandler({
      (call: FlutterMethodCall, result: @escaping FlutterResult) -> Void in
      if "getSharedData" == call.method {
           let userDefaults = UserDefaults(suiteName: "group.org.interestedparticipant.analyzeThis")
           let key = "analyzethisShareKey"
           if let data = userDefaults?.object(forKey: key) {
               result(data)
           } else {
               result(nil)
           }
      } else if "clearSharedData" == call.method {
           let userDefaults = UserDefaults(suiteName: "group.org.interestedparticipant.analyzeThis")
           let key = "analyzethisShareKey"
           userDefaults?.removeObject(forKey: key)
           result(true)
      } else {
        result(FlutterMethodNotImplemented)
      }
    })

    GeneratedPluginRegistrant.register(with: self)
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }
}
