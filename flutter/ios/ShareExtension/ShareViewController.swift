/*!
 * Native module for the share extension.
 * Adapted from open-source share extension implementations.
 */
import MobileCoreServices
import Photos
import Social
import UIKit
import UniformTypeIdentifiers

@objc(ShareViewController)
class ShareViewController: UIViewController {
  let hostAppGroupIdentifier = "group.org.interestedparticipant.analyzeThis"
  let shareProtocol = "analyzethis"
  let sharedKey = "analyzethisShareKey"
  
  // Data collected from all attachments
  var sharedMedia: [SharedMediaFile] = []
  var sharedWebUrl: [WebUrl] = []
  var sharedText: [String] = []
  
  // Content Types
  let imageContentType: String = UTType.image.identifier
  let videoContentType: String = UTType.movie.identifier
  let textContentType: String = UTType.text.identifier
  let urlContentType: String = UTType.url.identifier
  let propertyListType: String = UTType.propertyList.identifier
  let fileURLType: String = UTType.fileURL.identifier
  let pkpassContentType: String = "com.apple.pkpass"
  let pdfContentType: String = UTType.pdf.identifier
  let vcardContentType: String = "public.vcard"

  override func viewDidLoad() {
    super.viewDidLoad()
    // Directly handle input when view loads
    handleInput()
  }

  override func viewDidAppear(_ animated: Bool) {
    super.viewDidAppear(animated)
  }
    
  private func handleInput() {
      Task {
        guard let extensionContext = self.extensionContext,
          let content = extensionContext.inputItems.first as? NSExtensionItem,
          let attachments = content.attachments
        else {
          dismissWithError(message: "No content found")
          return
        }

        // Use a task group to process all attachments concurrently but wait for all to finish
        await withTaskGroup(of: Void.self) { group in
            for (index, attachment) in attachments.enumerated() {
                group.addTask {
                    if attachment.hasItemConformingToTypeIdentifier(self.imageContentType) {
                        await self.handleImages(content: content, attachment: attachment, index: index)
                    } else if attachment.hasItemConformingToTypeIdentifier(self.videoContentType) {
                        await self.handleVideos(content: content, attachment: attachment, index: index)
                    } else if attachment.hasItemConformingToTypeIdentifier(self.vcardContentType) {
                        await self.handleVCard(content: content, attachment: attachment, index: index)
                    } else if attachment.hasItemConformingToTypeIdentifier(self.fileURLType) {
                        await self.handleFiles(content: content, attachment: attachment, index: index)
                    } else if attachment.hasItemConformingToTypeIdentifier(self.pkpassContentType) {
                        await self.handlePkPass(content: content, attachment: attachment, index: index)
                    } else if attachment.hasItemConformingToTypeIdentifier(self.pdfContentType) {
                        await self.handlePdf(content: content, attachment: attachment, index: index)
                    } else if attachment.hasItemConformingToTypeIdentifier(self.propertyListType) {
                        await self.handlePrepocessing(content: content, attachment: attachment, index: index)
                    } else if attachment.hasItemConformingToTypeIdentifier(self.urlContentType) {
                        await self.handleUrl(content: content, attachment: attachment, index: index)
                    } else if attachment.hasItemConformingToTypeIdentifier(self.textContentType) {
                        await self.handleText(content: content, attachment: attachment, index: index)
                    } else {
                         NSLog("[ERROR] content type not handled: \(attachment.registeredTypeIdentifiers)")
                    }
                }
            }
        }
        
        // All tasks completed. Save and Redirect.
        self.saveAndRedirect()
      }
  }

  private func saveAndRedirect() {
      let combined = CombinedData(text: sharedText, webUrls: sharedWebUrl, media: sharedMedia)
      
      let userDefaults = UserDefaults(suiteName: self.hostAppGroupIdentifier)
      if let encoded = try? JSONEncoder().encode(combined) {
          userDefaults?.set(encoded, forKey: self.sharedKey)
          userDefaults?.synchronize()
      }
      
      // Determine redirect type based on priority: Media > WebUrl > Text
      var redirectType: RedirectType = .text
      if !sharedMedia.isEmpty {
          redirectType = .media
      } else if !sharedWebUrl.isEmpty {
          redirectType = .weburl
      } else if !sharedText.isEmpty {
          redirectType = .text
      }
      
      self.redirectToHostApp(type: redirectType)
  }

  private func handleVCard(content: NSExtensionItem, attachment: NSItemProvider, index: Int) async {
      do {
        if let url = try? await attachment.loadItem(forTypeIdentifier: self.vcardContentType) as? URL {
          let tmp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".vcf")
          _ = self.copyFile(at: url, to: tmp)
          await self.handleFileURL(content: content, url: tmp, index: index)
        } else if let data = try? await attachment.loadItem(forTypeIdentifier: self.vcardContentType) as? Data {
          let tmp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".vcf")
          try data.write(to: tmp)
          await self.handleFileURL(content: content, url: tmp, index: index)
        }
      } catch {
        NSLog("[ERROR] handleVCard exception: \(error.localizedDescription)")
      }
  }

  private func handleText(content: NSExtensionItem, attachment: NSItemProvider, index: Int) async {
      if let item = try? await attachment.loadItem(forTypeIdentifier: self.textContentType) as? String {
        await MainActor.run {
          self.sharedText.append(item)
        }
      }
  }

  private func handleUrl(content: NSExtensionItem, attachment: NSItemProvider, index: Int) async {
      if let item = try? await attachment.loadItem(forTypeIdentifier: self.urlContentType) as? URL {
          NSLog("[Debug] handleUrl: \(item.absoluteString)")
          
          // Enhanced Image Detection
          var isImage = false
          
          // 1. Check Path Extension
          if let type = UTType(filenameExtension: item.pathExtension), type.conforms(to: .image) {
              isImage = true
          }
          // 2. Check for common image extensions in the path (e.g. /image.webp) or path components
          else {
              let lowerPath = item.path.lowercased()
              let imageExtensions = ["png", "jpg", "jpeg", "gif", "webp", "heic"]
              
              // Check if path ends with extension
              if imageExtensions.contains(where: { lowerPath.hasSuffix(".\($0)") }) {
                  isImage = true
              }
              // Check if last path component IS the format (e.g. /format/webp or /format/webp/)
              else {
                  let lastComponent = item.lastPathComponent.lowercased()
                  if imageExtensions.contains(lastComponent) {
                      isImage = true
                  }
              }
          }

          if isImage {
              await self.processImage(url: item)
          } else {
              await MainActor.run {
                  self.sharedWebUrl.append(WebUrl(url: item.absoluteString, meta: ""))
              }
          }
      }
  }

  private func handlePrepocessing(content: NSExtensionItem, attachment: NSItemProvider, index: Int) async {
      if let item = try? await attachment.loadItem(forTypeIdentifier: self.propertyListType, options: nil) as? NSDictionary,
         let results = item[NSExtensionJavaScriptPreprocessingResultsKey] as? NSDictionary {
        
        await MainActor.run {
            self.sharedWebUrl.append(WebUrl(url: results["baseURI"] as! String, meta: results["meta"] as! String))
        }
      }
  }

  private func handlePkPass(content: NSExtensionItem, attachment: NSItemProvider, index: Int) async {
      do {
          if let url = try await attachment.loadItem(forTypeIdentifier: self.pkpassContentType) as? URL {
              await self.handleFileURL(content: content, url: url, index: index)
          } else if let data = try await attachment.loadItem(forTypeIdentifier: self.pkpassContentType) as? Data {
              let tempFileName = UUID().uuidString + ".pkpass"
              let tempFileURL = FileManager.default.temporaryDirectory.appendingPathComponent(tempFileName)
              try data.write(to: tempFileURL)
              await self.handleFileURL(content: content, url: tempFileURL, index: index)
          }
      } catch {
          NSLog("[ERROR] processing pkpass: \(error.localizedDescription)")
      }
  }

  private func handleImages(content: NSExtensionItem, attachment: NSItemProvider, index: Int) async {
      do {
        let item = try await attachment.loadItem(forTypeIdentifier: self.imageContentType)
        
        // Process on a background thread (implicitly), updating state on MainActor
        var url: URL? = nil
        
        if let dataURL = item as? URL {
            url = dataURL
        } else if let imageData = item as? UIImage {
            url = self.saveScreenshot(imageData)
        } else if let data = item as? Data {
            if let image = UIImage(data: data) {
                 url = self.saveScreenshot(image)
            }
        }

        guard let safeURL = url else { return }
        await self.processImage(url: safeURL)
      } catch {
        NSLog("[ERROR] handleImages: \(error)")
      }
  }
    
  private func processImage(url: URL) async {
      // Extract Metadata
      var pixelWidth: Int? = nil
      var pixelHeight: Int? = nil
      if let imageSource = CGImageSourceCreateWithURL(url as CFURL, nil) {
          if let imageProperties = CGImageSourceCopyPropertiesAtIndex(imageSource, 0, nil) as Dictionary? {
               pixelWidth = imageProperties[kCGImagePropertyPixelWidth] as? Int
               pixelHeight = imageProperties[kCGImagePropertyPixelHeight] as? Int
               
               if let orientationNumber = imageProperties[kCGImagePropertyOrientation] as! CFNumber? {
                    var orientation: Int = 0
                    CFNumberGetValue(orientationNumber, .intType, &orientation)
                    if orientation > 4 { // Rotate dimensions
                        let temp = pixelWidth
                        pixelWidth = pixelHeight
                        pixelHeight = temp
                    }
               }
          }
      }

      let fileName = self.getFileName(from: url, type: .image)
      let fileExtension = self.getExtension(from: url, type: .image)
      let fileSize = self.getFileSize(from: url)
      let mimeType = url.mimeType(ext: fileExtension)
      let newName = "\(UUID().uuidString).\(fileExtension)"
      let newPath = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: self.hostAppGroupIdentifier)!.appendingPathComponent(newName)
      
      if self.saveFile(at: url, to: newPath) {
           let mediaFile = SharedMediaFile(
               path: newPath.absoluteString, thumbnail: nil, fileName: fileName,
               fileSize: fileSize, width: pixelWidth, height: pixelHeight, duration: nil,
               mimeType: mimeType, type: .image)
           
           await MainActor.run {
               self.sharedMedia.append(mediaFile)
           }
      }
  }

  private func handleVideos(content: NSExtensionItem, attachment: NSItemProvider, index: Int) async {
      if let url = try? await attachment.loadItem(forTypeIdentifier: self.videoContentType) as? URL {
           let fileName = self.getFileName(from: url, type: .video)
           let fileExtension = self.getExtension(from: url, type: .video)
           let fileSize = self.getFileSize(from: url)
           let mimeType = url.mimeType(ext: fileExtension)
           let newName = "\(UUID().uuidString).\(fileExtension)"
           let newPath = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: self.hostAppGroupIdentifier)!.appendingPathComponent(newName)
           
           if self.copyFile(at: url, to: newPath) {
                if let sharedFile = self.getSharedMediaFile(forVideo: newPath, fileName: fileName, fileSize: fileSize, mimeType: mimeType) {
                     await MainActor.run {
                         self.sharedMedia.append(sharedFile)
                     }
                }
           }
      }
  }

  private func handlePdf(content: NSExtensionItem, attachment: NSItemProvider, index: Int) async {
      if let url = try? await attachment.loadItem(forTypeIdentifier: self.pdfContentType) as? URL {
          await self.handleFileURL(content: content, url: url, index: index)
      }
  }

  private func handleFiles(content: NSExtensionItem, attachment: NSItemProvider, index: Int) async {
      if let url = try? await attachment.loadItem(forTypeIdentifier: self.fileURLType) as? URL {
          await self.handleFileURL(content: content, url: url, index: index)
      }
  }

  private func handleFileURL(content: NSExtensionItem, url: URL, index: Int) async {
      let fileName = self.getFileName(from: url, type: .file)
      let fileExtension = self.getExtension(from: url, type: .file)
      let fileSize = self.getFileSize(from: url)
      let mimeType = url.mimeType(ext: fileExtension)
      let newName = "\(UUID().uuidString).\(fileExtension)"
      let newPath = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: self.hostAppGroupIdentifier)!.appendingPathComponent(newName)
      
      if self.copyFile(at: url, to: newPath) {
          let mediaFile = SharedMediaFile(
             path: newPath.absoluteString, thumbnail: nil, fileName: fileName,
             fileSize: fileSize, width: nil, height: nil, duration: nil, mimeType: mimeType,
             type: .file)
          
          await MainActor.run {
              self.sharedMedia.append(mediaFile)
          }
      }
  }

  private func dismissWithError(message: String? = nil) {
    DispatchQueue.main.async {
      let alert = UIAlertController(title: "Error", message: "Error loading application: \(message!)", preferredStyle: .alert)
      let action = UIAlertAction(title: "OK", style: .cancel) { _ in
        self.dismiss(animated: true, completion: nil)
        self.extensionContext!.completeRequest(returningItems: [], completionHandler: nil)
      }
      alert.addAction(action)
      self.present(alert, animated: true, completion: nil)
    }
  }

  private func redirectToHostApp(type: RedirectType) {
    let url = URL(string: "\(shareProtocol)://dataUrl=\(sharedKey)#\(type)")!
    var responder = self as UIResponder?

    while responder != nil {
      if let application = responder as? UIApplication {
        if application.canOpenURL(url) {
          application.open(url)
        } else {
            // If we can't open, just finish
        }
      }
      responder = responder!.next
    }
    extensionContext!.completeRequest(returningItems: [], completionHandler: nil)
  }

  // Helpers
  private func saveScreenshot(_ image: UIImage) -> URL? {
    guard let screenshotData = image.pngData() else { return nil }
    guard let containerURL = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: self.hostAppGroupIdentifier) else { return nil }
    let fileName = "screenshot_\(UUID().uuidString).png"
    let screenshotPath = containerURL.appendingPathComponent(fileName)
    do {
      try screenshotData.write(to: screenshotPath)
      return screenshotPath
    } catch {
      return nil
    }
  }
  
  func getExtension(from url: URL, type: SharedMediaType) -> String {
    let parts = url.lastPathComponent.components(separatedBy: ".")
    if parts.count > 1 { return parts.last! }
    switch type {
      case .image: return "PNG"
      case .video: return "MP4"
      case .file: return "TXT"
    }
  }

  func getFileName(from url: URL, type: SharedMediaType) -> String {
    var name = url.lastPathComponent
    if name == "" { name = UUID().uuidString + "." + getExtension(from: url, type: type) }
    return name
  }

  func getFileSize(from url: URL) -> Int? {
    let resources = try? url.resourceValues(forKeys: [.fileSizeKey])
    return resources?.fileSize
  }

  func saveFile(at srcURL: URL, to dstURL: URL) -> Bool {
    do {
      if FileManager.default.fileExists(atPath: dstURL.path) {
        try FileManager.default.removeItem(at: dstURL)
      }
      
      if srcURL.isFileURL {
          try FileManager.default.copyItem(at: srcURL, to: dstURL)
      } else {
          // Download remote file
          let data = try Data(contentsOf: srcURL)
          try data.write(to: dstURL)
      }
      return true
    } catch {
      NSLog("[ERROR] saveFile failed: \(error)")
      return false
    }
  }
    
  // Deprecated: use saveFile instead
  func copyFile(at srcURL: URL, to dstURL: URL) -> Bool {
      return saveFile(at: srcURL, to: dstURL)
  }

  private func getSharedMediaFile(forVideo: URL, fileName: String, fileSize: Int?, mimeType: String) -> SharedMediaFile? {
      let asset = AVAsset(url: forVideo)
      let duration = (CMTimeGetSeconds(asset.duration) * 1000).rounded()
      let track = asset.tracks(withMediaType: AVMediaType.video).first
      var width: Int? = nil, height: Int? = nil
      if let t = track {
          let size = t.naturalSize.applying(t.preferredTransform)
          width = abs(Int(size.width))
          height = abs(Int(size.height))
      }
      
      let thumbnailPath = getThumbnailPath(for: forVideo)
      if FileManager.default.fileExists(atPath: thumbnailPath.path) {
          return SharedMediaFile(path: forVideo.absoluteString, thumbnail: thumbnailPath.absoluteString, fileName: fileName, fileSize: fileSize, width: width, height: height, duration: duration, mimeType: mimeType, type: .video)
      }
      
      // Generate thumbnail
      let generator = AVAssetImageGenerator(asset: asset)
      generator.appliesPreferredTrackTransform = true
      generator.maximumSize = CGSize(width: 360, height: 360)
      if let img = try? generator.copyCGImage(at: CMTimeMake(value: 0, timescale: 1), actualTime: nil),
         let data = UIImage(cgImage: img).pngData() {
          try? data.write(to: thumbnailPath)
          return SharedMediaFile(path: forVideo.absoluteString, thumbnail: thumbnailPath.absoluteString, fileName: fileName, fileSize: fileSize, width: width, height: height, duration: duration, mimeType: mimeType, type: .video)
      }
      return nil
  }

  private func getThumbnailPath(for url: URL) -> URL {
    let fileName = Data(url.lastPathComponent.utf8).base64EncodedString().replacingOccurrences(of: "==", with: "")
    return FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: self.hostAppGroupIdentifier)!.appendingPathComponent("\(fileName).jpg")
  }

  enum RedirectType { case media, text, weburl, file }
  enum SharedMediaType: Int, Codable { case image, video, file }

  // New Combined Data Structure
  struct CombinedData: Codable {
      var text: [String]
      var webUrls: [WebUrl]
      var media: [SharedMediaFile]
  }

  class WebUrl: Codable {
    var url: String
    var meta: String
    init(url: String, meta: String) { self.url = url; self.meta = meta }
  }

  class SharedMediaFile: Codable {
    var path: String
    var thumbnail: String?
    var fileName: String
    var fileSize: Int?
    var width: Int?
    var height: Int?
    var duration: Double?
    var mimeType: String
    var type: SharedMediaType

    init(path: String, thumbnail: String?, fileName: String, fileSize: Int?, width: Int?, height: Int?, duration: Double?, mimeType: String, type: SharedMediaType) {
      self.path = path; self.thumbnail = thumbnail; self.fileName = fileName; self.fileSize = fileSize
      self.width = width; self.height = height; self.duration = duration; self.mimeType = mimeType; self.type = type
    }
  }
}

internal let mimeTypes = [
  "html": "text/html",
  "htm": "text/html",
  "shtml": "text/html",
  "css": "text/css",
  "xml": "text/xml",
  "gif": "image/gif",
  "jpeg": "image/jpeg",
  "jpg": "image/jpeg",
  "js": "application/javascript",
  "atom": "application/atom+xml",
  "rss": "application/rss+xml",
  "mml": "text/mathml",
  "txt": "text/plain",
  "jad": "text/vnd.sun.j2me.app-descriptor",
  "wml": "text/vnd.wap.wml",
  "htc": "text/x-component",
  "png": "image/png",
  "tif": "image/tiff",
  "tiff": "image/tiff",
  "wbmp": "image/vnd.wap.wbmp",
  "ico": "image/x-icon",
  "jng": "image/x-jng",
  "bmp": "image/x-ms-bmp",
  "svg": "image/svg+xml",
  "svgz": "image/svg+xml",
  "webp": "image/webp",
  "woff": "application/font-woff",
  "jar": "application/java-archive",
  "war": "application/java-archive",
  "ear": "application/java-archive",
  "json": "application/json",
  "hqx": "application/mac-binhex40",
  "doc": "application/msword",
  "pdf": "application/pdf",
  "ps": "application/postscript",
  "eps": "application/postscript",
  "ai": "application/postscript",
  "rtf": "application/rtf",
  "m3u8": "application/vnd.apple.mpegurl",
  "xls": "application/vnd.ms-excel",
  "eot": "application/vnd.ms-fontobject",
  "ppt": "application/vnd.ms-powerpoint",
  "wmlc": "application/vnd.wap.wmlc",
  "kml": "application/vnd.google-earth.kml+xml",
  "kmz": "application/vnd.google-earth.kmz",
  "7z": "application/x-7z-compressed",
  "cco": "application/x-cocoa",
  "jardiff": "application/x-java-archive-diff",
  "jnlp": "application/x-java-jnlp-file",
  "pkpass": "application/vnd.apple.pkpass",
  "run": "application/x-makeself",
  "pl": "application/x-perl",
  "pm": "application/x-perl",
  "prc": "application/x-pilot",
  "pdb": "application/x-pilot",
  "rar": "application/x-rar-compressed",
  "rpm": "application/x-redhat-package-manager",
  "sea": "application/x-sea",
  "swf": "application/x-shockwave-flash",
  "sit": "application/x-stuffit",
  "tcl": "application/x-tcl",
  "tk": "application/x-tcl",
  "der": "application/x-x509-ca-cert",
  "pem": "application/x-x509-ca-cert",
  "crt": "application/x-x509-ca-cert",
  "xpi": "application/x-xpinstall",
  "xhtml": "application/xhtml+xml",
  "xspf": "application/xspf+xml",
  "zip": "application/zip",
  "epub": "application/epub+zip",
  "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "mid": "audio/midi",
  "midi": "audio/midi",
  "kar": "audio/midi",
  "mp3": "audio/mpeg",
  "ogg": "audio/ogg",
  "m4a": "audio/x-m4a",
  "ra": "audio/x-realaudio",
  "3gpp": "video/3gpp",
  "3gp": "video/3gpp",
  "ts": "video/mp2t",
  "mp4": "video/mp4",
  "mpeg": "video/mpeg",
  "mpg": "video/mpeg",
  "mov": "video/quicktime",
  "webm": "video/webm",
  "flv": "video/x-flv",
  "m4v": "video/x-m4v",
  "mng": "video/x-m4v",
  "asx": "video/x-ms-asf",
  "asf": "video/x-ms-asf",
  "wmv": "video/x-ms-wmv",
  "avi": "video/x-msvideo",
  "vcf": "text/vcard",
]

extension URL {
  func mimeType(ext: String?) -> String {
    if #available(iOSApplicationExtension 14.0, *) {
      if let pathExt = ext, let mimeType = UTType(filenameExtension: pathExt)?.preferredMIMEType {
        return mimeType
      }
    }
    return mimeTypes[ext?.lowercased() ?? ""] ?? "application/octet-stream"
  }
}
