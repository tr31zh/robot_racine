
/*
  WiFi Controller for Robot racine
  by Felicià Maviane Macia
 */

#include <SPI.h>
#include <Ethernet.h>
#include <EthernetUdp.h>

int STOP = 2; // for stopping the step motor
int ORIGIN = 6; // for sensing plate #1 at origin position
int IMGPOS = 9; // for sensing a plate at imaging position

bool SIM_MODE = true;

// Simulation code  
int whiteLed = 1; // In transition
int greenLed = 3; // Start
int bluLed = 5; // Home
int yellowLed = 8; // Next
int timeOutIter = 200; // 

int nextAlreadyTriggered = 0;

byte mac[] = { 0xA8, 0x61, 0x0A, 0xAE, 0x6D, 0xB3 }; //physical mac address
byte ip[] = {192, 168, 0, 21};

// UDP
unsigned int localPort = 2390;
char packetBuffer[256]; //buffer to hold incoming packet
char  ReplyBuffer[] = "stopped"; // a string to send back

EthernetServer server(80);
EthernetUDP Udp;

void setup() {

  //Initialize serial and wait for port to open:
  Serial.begin(9600);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }

  // Start Ethernet server
  Serial.println("Access Point Web Server");
  Ethernet.begin(mac, ip);
  Serial.print("IP Address: ");
  Serial.println(Ethernet.localIP());
  Serial.print("To see this page in action, open a browser to http://");
  Serial.println(Ethernet.localIP());
  server.begin();

  // Start UDP connexion
  Udp.begin(localPort);

  pinMode(STOP, OUTPUT);
  if (SIM_MODE) { // Simulation code  
    pinMode(bluLed, OUTPUT);
    pinMode(greenLed, OUTPUT);
    pinMode(yellowLed, OUTPUT);
    pinMode(whiteLed, OUTPUT);
    pinMode(IMGPOS, INPUT_PULLUP);  
    pinMode(ORIGIN, INPUT_PULLUP);  
  } else {
    pinMode(IMGPOS, INPUT);  
    pinMode(ORIGIN, INPUT);      
  }
  digitalWrite(STOP, HIGH);
}

void loop() {

  if (checkStopCommand() == 1) {
    doStop();
    exit;
  }
  
  String received_command = "";
  
  EthernetClient client = server.available();
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

        if (currentLine.endsWith("GET /")) {
          received_command = "";
        }
      }
    }

    if (received_command == "start") {
      Serial.println("Reponding to start command");
      doStart(client);
    }

    if (received_command == "stop") {
      Serial.println("Reponding to stop command");
      doStop();      
      buildResponse(client, "stop");
    }

    if (received_command == "") {
      Serial.println("Reponding to no command, displaying default page");
      buildResponse(client, "");
    }

    if (received_command == "go_home") {
      Serial.println("Reponding to go home command");
      doGoHome(client);      
    }

    if (received_command == "go_next") {
      Serial.println("Reponding to go next command");
      doGoNext(client);      
    }

    // close the connection:
    client.stop();
    Serial.println("client disconnected");
    Serial.println("___________________");
  }
}

void buildResponse(EthernetClient client, String msg) {
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

void setState(int stopState, int bl, int gl, int yl, int wl) {
  digitalWrite(STOP, stopState);
  if (SIM_MODE) { // Simulation code  
    digitalWrite(bluLed, bl);
    digitalWrite(greenLed, gl);
    digitalWrite(yellowLed, yl);  
    digitalWrite(whiteLed, wl);  
  }
}

void doStart(EthernetClient client) {
  setState(LOW, LOW, HIGH, LOW, LOW);
  buildResponse(client, "start");
}

void doStop() {
  setState(HIGH, LOW, LOW, LOW, LOW);
}

void doGoHome(EthernetClient client) {
  int homeSensor = digitalRead(ORIGIN);
  if (homeSensor == LOW) {
    buildResponse(client, "go_home");
  } else {
    setState(LOW, LOW, HIGH, LOW, HIGH);
    int homeSensor = digitalRead(ORIGIN);
    int aux = 0;
    int stop_requested = 0;
    int count_attempts = 0;
    while (homeSensor == HIGH) {
      homeSensor = digitalRead(ORIGIN);
      delay(10);
      if (SIM_MODE) { // Simulation code  
        if (aux < 40) {
          digitalWrite(bluLed, HIGH);
        }
        if (aux > 40) {
          digitalWrite(bluLed, LOW);
        }
      }
      if (aux > 80) {
        aux = 0;
      } else {
        aux++;
      }
      if (checkStopCommand() == 1) {
        stop_requested = 1;
        break;
      }
      // If no board is present simulate button pressing with a time out
      count_attempts++;
      if (count_attempts >= timeOutIter) {
        Serial.println("Button waiting Time out");
        break;
      }
    }
    doStop();
    if (SIM_MODE) { // Simulation code  
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
}

void doGoNext(EthernetClient client) {
  setState(LOW, LOW, HIGH, LOW, HIGH);
  delay(500);
  int nextSensor = digitalRead(IMGPOS);
  int aux = 0;
  int stop_requested = 0;
  int count_attempts = 0;
  while (nextSensor == HIGH) {
    nextSensor = digitalRead(IMGPOS);
    delay(10);
    if (SIM_MODE) { // Simulation code  
      if (aux < 40) {
        digitalWrite(yellowLed, HIGH);
      }
      if (aux > 40) {
        digitalWrite(yellowLed, LOW);
      }
    }
    if (aux > 80) {
      aux = 0;
    } else {
      aux++;
    }
    if (checkStopCommand() == 1) {      
      stop_requested = 1;
      break;
    }
    // If no board is present simulate button pressing with a time out
    count_attempts++;
    if (count_attempts >= timeOutIter) {
      Serial.println("Button waiting Time out");
      break;
    }
  }
  doStop();
  if (SIM_MODE) { // Simulation code  
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
