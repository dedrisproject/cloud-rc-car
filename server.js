// Importing the required modules
const WebSocketServer = require('ws');
var Gpio = require('onoff').Gpio; //include onoff to interact with the GPIO
var LED = new Gpio(17, 'out'); //use GPIO pin 4, and specify that it is output
const { exec } = require('child_process');
var ultimocomando = '0';


// Creating a new websocket server
const wss = new WebSocketServer.Server({ port: 8080 })

// Creating connection using websocket
wss.on("connection", ws => {
    console.log("new client connected");
    // sending message
    ws.on("message", data => {
        console.log(`recived: ${data}`)
setTimeout(() => {
if (data == "5") { // Accendo i fari

if (LED.readSync() === 0) { //check the pin state, if the state is 0 (or off)
    LED.writeSync(1); //set pin state to 1 (turn LED on)
        console.log('accendo i fari')
  }
} else { // Accendo i fari
if (LED.readSync() === 1) { //check the pin state, if the s>
    LED.writeSync(0); //set pin state to 1 (turn LED on)
  }
}

if (data == "4") { // Spengo i fari
if (LED.readSync() === 1) { //check the pin state, if the s>
    LED.writeSync(0); //set pin state to 1 (turn LED on)
console.log('spengo i fari')

  }
}

if (data == "7" && ultimocomando != "7") { // Tasto 0
        console.log('Invio comando Accelera')
        var ultimocomando = "7";
        exec('sudo echo -ne "7|" > /dev/ttyACM0');
}

if (data == "6" && ultimocomando != "6") { // Tasto 0
        console.log('Invio comando Frena')
        var ultimocomando = "6";
        exec('sudo echo -ne "6|" > /dev/ttyACM0');
}

if (data == "1" && ultimocomando != "1") { // Tasto 0
        console.log('Invio comando Retromarcia')
        var ultimocomando = "1";
        exec('sudo echo -ne "1|" > /dev/ttyACM0');
}


if (data == "15" && ultimocomando != "15") { // Tasto 0
        console.log('Invio comando Sterza a destra')
        var ultimocomando = "15";
        exec('sudo echo -ne "15|" > /dev/ttyACM0');
}

if (data == "14" && ultimocomando != "14") { // Tasto 0
        console.log('Invio comando Sterza a sinistra')
        var ultimocomando = "14";
        exec('sudo echo -ne "14|" > /dev/ttyACM0');
}

if (data == "12" && ultimocomando != "12") { // Tasto 0
        console.log('Invio comando Ruote al centro')
        var ultimocomando = "12";
        exec('sudo echo -ne "12|" > /dev/ttyACM0');
}

console.log(ultimocomando);

}, "10")
    });
    // handling what to do when clients disconnects from server
    ws.on("close", () => {
        console.log("the client has connected");
    });
    // handling client connection error
    ws.onerror = function () {
        console.log("Some Error occurred")
    }
});
console.log("Macchina in ascolto sulla porta 8080");



