import AppKit

let cardWidth = 96.0, cardHeight = 54.0, inset = 8.0, pollSeconds = 1.0, requestTimeout = 2.0
let eyeWidth = 14.0, eyeHeight = 6.0, faceRadius = 12.0, lineWidth = 2.0
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let panel = NSPanel(contentRect: NSRect(x:0,y:0,width:cardWidth,height:cardHeight), styleMask:[.borderless,.nonactivatingPanel],backing:.buffered,defer:false)
panel.level = NSWindow.Level(rawValue:NSWindow.Level.statusBar.rawValue + 1)
panel.collectionBehavior = [.canJoinAllSpaces,.fullScreenAuxiliary,.stationary]
panel.isOpaque = false; panel.backgroundColor = .clear; panel.ignoresMouseEvents = true
final class Face: NSView {
 override func draw(_ rect: NSRect) {
  NSColor(calibratedRed:0.03,green:0.09,blue:0.14,alpha:0.96).setFill()
  NSBezierPath(roundedRect:bounds,xRadius:faceRadius,yRadius:faceRadius).fill()
  NSColor.cyan.setStroke(); NSColor.cyan.setFill()
  for x in [cardWidth/3-eyeWidth/2,cardWidth*2/3-eyeWidth/2] {
   NSBezierPath(roundedRect:NSRect(x:x,y:cardHeight/2,width:eyeWidth,height:eyeHeight),xRadius:lineWidth,yRadius:lineWidth).fill()
  }
  let mouth=NSBezierPath();mouth.move(to:NSPoint(x:cardWidth/3,y:cardHeight/3));mouth.line(to:NSPoint(x:cardWidth*2/3,y:cardHeight/3));mouth.lineWidth=lineWidth;mouth.stroke()
 }
}
panel.contentView = Face(frame:panel.contentView!.bounds)
var inFlight = false
func poll() {
 guard !inFlight else {return};inFlight=true
 var request=URLRequest(url:URL(string:"http://127.0.0.1:4700/watch")!);request.timeoutInterval=requestTimeout
 URLSession.shared.dataTask(with:request){data,_,_ in
  let state=data.flatMap{try? JSONSerialization.jsonObject(with:$0) as? [String:Any]}
  DispatchQueue.main.async {
   inFlight=false
   guard state?["active"] as? Bool == true,let screen=NSScreen.screens.first else {panel.orderOut(nil);app.terminate(nil);return}
   panel.setFrameOrigin(NSPoint(x:screen.frame.maxX-cardWidth-inset,y:screen.frame.maxY-cardHeight))
   panel.orderFrontRegardless()
  }
 }.resume()
}
let timer=Timer.scheduledTimer(withTimeInterval:pollSeconds,repeats:true){_ in poll()}
poll();app.run()
