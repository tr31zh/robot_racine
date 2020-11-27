
/*
  WiFi Controller for Robot racine
  by Felicià Maviane Macia
 */

#include <SPI.h>
#include <WiFiNINA.h>
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

WiFiServer server(80);

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

  // you're connected now, so print out the status
  printWiFiStatus();
}

void loop() {

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
  
  WiFiClient client = server.available();   // listen for incoming clients
  if (client) {                             // if you get a client,
    String currentLine = "";                // make a String to hold incoming data from the client
    while (client.connected()) {            // loop while the client's connected
      if (client.available()) {             // if there's bytes to read from the client,
        char c = client.read();             // read a byte, then
        Serial.write(c);                    // print it out the serial monitor
        if (c == '\n') {                    // if the byte is a newline character
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
      digitalWrite(bluLed, LOW);
      digitalWrite(redLed, LOW);
      digitalWrite(greenLed, HIGH);
      digitalWrite(yellowLed, LOW);
      buildResponse(client, received_command);
    }

    if (received_command == "stop") {
      digitalWrite(bluLed, LOW);
      digitalWrite(redLed, HIGH);
      digitalWrite(greenLed, LOW);
      digitalWrite(yellowLed, LOW);
      buildResponse(client, received_command);
      delay(500);
      digitalWrite(redLed, LOW);
    }

    if (received_command == "go_home") {
      digitalWrite(bluLed, LOW);
      digitalWrite(redLed, LOW);
      digitalWrite(greenLed, HIGH);
      digitalWrite(yellowLed, LOW);
      digitalWrite(whiteLed, HIGH);
      int homeSensor = digitalRead(buttonHome);
      while (homeSensor == HIGH) {
        homeSensor = digitalRead(buttonHome);
        delay(10);
      }
      digitalWrite(bluLed, HIGH);
      digitalWrite(whiteLed, LOW);      
      digitalWrite(greenLed, LOW);
      buildResponse(client, received_command);
    }

    if (received_command == "go_next") {
      digitalWrite(bluLed, LOW);
      digitalWrite(redLed, LOW);
      digitalWrite(greenLed, HIGH);
      digitalWrite(yellowLed, LOW);
      digitalWrite(whiteLed, HIGH);
      delay(500);
      int nextSensor = digitalRead(buttonNext);
      while (nextSensor == HIGH) {
        nextSensor = digitalRead(buttonNext);
        delay(10);
      }
      digitalWrite(yellowLed, HIGH);
      digitalWrite(whiteLed, LOW);
      digitalWrite(greenLed, LOW);
      buildResponse(client, received_command);
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
  client.print("Click <a href=\"/start\">here</a> Start (turn green LED on)<br>");
  client.print("Click <a href=\"/stop\">here</a> Stop (turn red LED on)<br>");
  client.print("Click <a href=\"/go_next\">here</a> Go next (turn yellow LED on)<br>");
  client.print("Click <a href=\"/go_home\">here</a> Go home (turn blue LED on)<br>");
  client.print(msg);
  client.println();
  client.println();
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
