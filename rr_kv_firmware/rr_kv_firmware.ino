
/*
  WiFi Controller for Robot racine
  by Felicià Maviane Macia
 */

#include <SPI.h>
#include <WiFiNINA.h>
#include <WiFiUdp.h>
#include "wifi_credentials.h" 

///////please enter your sensitive data in the Secret tab/arduino_secrets.h
char ssid[] = SECRET_SSID;        // your network SSID (name)
char pass[] = SECRET_PASS;    // your network password (use for WPA, or use as key for WEP)
int keyIndex = 0;                // your network key Index number (needed only for WEP)

// SD
int bluLed = 7; // Home
int redLed = 3; // Stop
int greenLed = 5; // Start
int yellowLed = 11; // Next
int whiteLed = 1; // In transition

int buttonNext = 12;
int buttonHome = 8;


int status = WL_IDLE_STATUS;
int nextAlreadyTriggered = 0;

// UDP
unsigned int localPort = 2390;
char packetBuffer[256]; //buffer to hold incoming packet
char  ReplyBuffer[] = "stopped"; // a string to send back

WiFiServer server(80);
WiFiUDP Udp;

void setup() {

  //Initialize serial and wait for port to open:
  Serial.begin(9600);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }

  Serial.println("Access Point Web Server");

  // SD  
  pinMode(bluLed, OUTPUT);
  pinMode(redLed, OUTPUT);
  pinMode(greenLed, OUTPUT);
  pinMode(yellowLed, OUTPUT);
  pinMode(whiteLed, OUTPUT);
  pinMode(buttonNext, INPUT_PULLUP);  
  pinMode(buttonHome, INPUT_PULLUP);  

  // check for the WiFi module:
  if (WiFi.status() == WL_NO_MODULE) {
    Serial.println("Communication with WiFi module failed!");
    // don't continue
    while (true);
  }

  String fv = WiFi.firmwareVersion();
  if (fv < WIFI_FIRMWARE_LATEST_VERSION) {
    Serial.println("Please upgrade the firmware");
  }

  // attempt to connect to Wifi network:
  while (status != WL_CONNECTED) {
    Serial.print("Attempting to connect to WPA SSID: ");
    Serial.println(ssid);
    // Connect to WPA/WPA2 network:
    status = WiFi.begin(ssid, pass);

    // wait 10 seconds for connection:
    delay(10000);
  }

  // start the web server on port 80
  server.begin();

  // Start UDP connexion
  Udp.begin(localPort);

  // you're connected now, so print out the status
  printWiFiStatus();
}

void loop() {

  if (checkStopCommand() == 1) {
    doStop();
    exit;
  }
  
  // compare the previous status to the current status
  if (status != WiFi.status()) {
    // it has changed update the variable
    status = WiFi.status();
    if (status == WL_AP_CONNECTED) {
      // a device has connected to the AP
      Serial.println("Device connected to AP");
    } else {
      // a device has disconnected from the AP, and we are back in listening mode
      Serial.println("Device disconnected from AP");
    }
  }

  String received_command = "";
  
  WiFiClient client = server.available();
  if (client) {
    String currentLine = "";
    while (client.connected()) {
      if (client.available()) {
        char c = client.read();
        Serial.write(c);
        if (c == '\n') {
          if (currentLine.length() == 0) {            
            break;
          }
          else {
            currentLine = "";
          }
        }
        else if (c != '\r') {
          currentLine += c;
        }
        
        if (currentLine.endsWith("GET /stop")) {
          received_command = "stop";
        }

        if (currentLine.endsWith("GET /go_home")) {
          received_command = "go_home";
        }

        if (currentLine.endsWith("GET /go_next")) {
          received_command = "go_next";
        }

        if (currentLine.endsWith("GET /start")) {
          received_command = "start";
        }
      }
    }

    if (received_command == "start") {
      doStart(client);
    }

    if (received_command == "stop") {
      doStop();      
      buildResponse(client, "stop");
    }

    if (received_command == "go_home") {
      doGoHome(client);      
    }

    if (received_command == "go_next") {
      doGoNext(client);      
    }

    // close the connection:
    client.stop();
    Serial.println("client disconnected");
    Serial.println("___________________");
  }
}

void buildResponse(WiFiClient client, String msg) {
  client.println("HTTP/1.1 200 OK");
  client.println("Content-type:text/html");
  client.println();
  // the content of the HTTP response follows the header:
  client.print("  <!DOCTYPE html>");
  client.print("<html lang=\"en\">");
  client.print("<head>");
  client.print("  <title>Bootstrap Example</title>");
  client.print("  <meta charset=\"utf-8\">");
  client.print("  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">");
  client.print("  <link rel=\"stylesheet\" href=\"https://maxcdn.bootstrapcdn.com/bootstrap/3.4.1/css/bootstrap.min.css\">");
  client.print("  <script src=\"https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js\"></script>");
  client.print("  <script src=\"https://maxcdn.bootstrapcdn.com/bootstrap/3.4.1/js/bootstrap.min.js\"></script>");
  client.print("</head>");
  client.print("<body>");
  client.print("");
  client.print("<div class=\"container\">");
  client.print("  <h2>Manual command overrides</h2>");
  client.print("  <a href=\"/start\" class=\"btn btn-success\" role=\"button\">Start (turn green LED on)</a><br><br>");
  client.print("  <a href=\"/stop\" class=\"btn btn-danger\" role=\"button\">Stop (turn red LED on)</a><br><br>");
  client.print("  <a href=\"/go_next\" class=\"btn btn-warning\" role=\"button\">Go next (turn yellow LED on)</a><br><br>");
  client.print("  <a href=\"/go_home\" class=\"btn btn-primary\" role=\"button\">Go home (turn blue LED on)</a><br><br>");
  client.print("</div>");
  client.print("");
  client.print("</body>");
  client.println("</html><br>");
  client.print(msg);
  client.println();
  client.println();
}

void doStart(WiFiClient client) {
  digitalWrite(bluLed, LOW);
  digitalWrite(redLed, LOW);
  digitalWrite(greenLed, HIGH);
  digitalWrite(yellowLed, LOW);
  buildResponse(client, "start");
}

void doStop() {
  digitalWrite(bluLed, LOW);
  digitalWrite(redLed, HIGH);
  digitalWrite(greenLed, LOW);
  digitalWrite(yellowLed, LOW);
  delay(500);
  digitalWrite(redLed, LOW);
}

void doGoHome(WiFiClient client) {
  int homeSensor = digitalRead(buttonHome);
  if (homeSensor == LOW) {
    buildResponse(client, "go_home");
  } else {
    digitalWrite(bluLed, LOW);
    digitalWrite(redLed, LOW);
    digitalWrite(greenLed, HIGH);
    digitalWrite(yellowLed, LOW);
    digitalWrite(whiteLed, HIGH);
    int homeSensor = digitalRead(buttonHome);
    int aux = 0;
    int stop_requested = 0;
    while (homeSensor == HIGH) {
      homeSensor = digitalRead(buttonHome);
      delay(10);
      if (aux < 40) {
        digitalWrite(bluLed, HIGH);
      }
      if (aux > 40) {
        digitalWrite(bluLed, LOW);
      }
      if (aux > 80) {
        aux = 0;
      } else {
        aux++;
      }
      if (checkStopCommand() == 1) {
        doStop();
        stop_requested = 1;
        break;
      }
    }
    digitalWrite(whiteLed, LOW);
    digitalWrite(greenLed, LOW);
    if (stop_requested == 1) {
      digitalWrite(bluLed, LOW);
      buildResponse(client, "stopped");
    } else {
      digitalWrite(bluLed, HIGH);
      buildResponse(client, "go_home");
    }  
  }
}

void doGoNext(WiFiClient client) {
  digitalWrite(bluLed, LOW);
  digitalWrite(redLed, LOW);
  digitalWrite(greenLed, HIGH);
  digitalWrite(yellowLed, LOW);
  digitalWrite(whiteLed, HIGH);
  delay(500);
  int nextSensor = digitalRead(buttonNext);
  int aux = 0;
  int stop_requested = 0;
  while (nextSensor == HIGH) {
    nextSensor = digitalRead(buttonNext);
    delay(10);        
    if (aux < 40) {
      digitalWrite(yellowLed, HIGH);
    }
    if (aux > 40) {
      digitalWrite(yellowLed, LOW);
    }
    if (aux > 80) {
      aux = 0;
    } else {
      aux++;
    }
    if (checkStopCommand() == 1) {
      doStop();
      stop_requested = 1;
      break;
    }
  }
  digitalWrite(whiteLed, LOW);
  digitalWrite(greenLed, LOW);
  if (stop_requested == 1) {
    digitalWrite(yellowLed, LOW);
    buildResponse(client, "stopped");
  } else {
    digitalWrite(yellowLed, HIGH);
    buildResponse(client, "go_next");
  }  
}

int checkStopCommand() {
  int packetSize = Udp.parsePacket();
  if (packetSize) {
    Serial.print("Received packet of size ");
    Serial.println(packetSize);
    Serial.print("From ");
    IPAddress remoteIp = Udp.remoteIP();
    Serial.print(remoteIp);
    Serial.print(", port ");
    Serial.println(Udp.remotePort());

    // read the packet into packetBufffer
    int len = Udp.read(packetBuffer, 255);
    if (len > 0) {
      packetBuffer[len] = 0;
    }
    Serial.println("Contents:");
    Serial.println(packetBuffer);

    // send a reply, to the IP address and port that sent us the packet we received
    Udp.beginPacket(Udp.remoteIP(), Udp.remotePort());
    Udp.write(ReplyBuffer);
    Udp.endPacket();

    return 1;
  } else {
    return 0; 
  }
}

void printWiFiStatus() {
  // print the SSID of the network you're attached to:
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());

  // print your WiFi shield's IP address:
  IPAddress ip = WiFi.localIP();
  Serial.print("IP Address: ");
  Serial.println(ip);

  // print where to go in a browser:
  Serial.print("To see this page in action, open a browser to http://");
  Serial.println(ip);
}
