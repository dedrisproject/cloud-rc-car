<html>
<head>
<title>Cloud Car</title>
<script src="jquery.js"></script>
</head>
<body>
<div style="float:left; width:70%; background:#ccc; height:600px;">
<iframe src="http://192.168.1.124:3000/" style="width:100%; height:100%;"></iframe>
</div>
<fieldset>
<legend style="float:left; width:30%;">

</legend>
<div id="gamepad">
<h1>Nessun Controller connesso</h1>
</div>
</fieldset>

<div id="socketconsole" style="border:1px solid #ccc; width:30%; float:left; height:200px">
</div>
<button type="button" onClick="testsocket();">Test Socket</button>
</body>
</html>

<script type="text/javascript">


document.onkeydown = checkKey;

function checkKey(e) {

    e = e || window.event;

    if (e.keyCode == '38') {
        // up arrow
		socket.send("7");
    }
    else if (e.keyCode == '40') {
        // down arrow
		socket.send("6");
    }
    else if (e.keyCode == '37') {
       // left arrow
	   
    }
    else if (e.keyCode == '39') {
       // right arrow
    }

}

 

// global gamepad object
let gamepadIndex;
window.addEventListener('gamepadconnected', (event) => {
	gamepadIndex = event.gamepad.index;
});

setInterval(() => {
	if(gamepadIndex !== undefined) {
		// a gamepad is connected and has an index
		const myGamepad = navigator.getGamepads()[gamepadIndex];
		//document.body.innerHTML = ""; // reset page
		$("#gamepad").html("");
	
		myGamepad.buttons.map(e => e.pressed).forEach((isPressed, buttonIndex) => {
			if(isPressed) {
				// button is pressed; indicate this on the page
				//document.body.innerHTML += `<h1>Button ${buttonIndex} is pressed</h1>`;
				$("#gamepad").html( `<h1>Button ${buttonIndex} is pressed</h1>`);
				//sendbutton(buttonIndex);
				socket.send(buttonIndex);
				console(buttonIndex);
			} 
		})
	}
}, 100) // print buttons that are pressed 10 times per second
</script>

<script>

let socket = new WebSocket("ws://192.168.1.124:8080");
console.log(socket.readyState);
socket.onmessage = function(e){ console.log(e.data); };
console.log(socket.readyState);
socket.onopen = () => conn.send('hello');

socket.onmessage = function(event) {
  //lert(`[message] Ricezione dati dal server: ${event.data}`);
  $("#socketconsole").append("Ricezione dati dal server: "+event.data+"<br>");
  console.log("Ricezione dati dal server: "+event.data);
};

socket.onclose = function(event) {
  if (event.wasClean) {
    //alert(`[close] Connessione chiusa con successo, code=${event.code} reason=${event.reason}`);
	$("#socketconsole").append("Connessione chiusa: "+event.code+"<br>")  
	console.log(socket.readyState);
} else {
    // e.g. processo del server terminato o connessione già
    // in questo caso event.code  è 1006
   //  alert('[close] Connection morta.');
	$("#socketconsole").append("Server Socket offline<br>")  
	console.log(socket.readyState);
  }
};


socket.onopen = function(e) {
  alert("[open] Connessione stabilita");
  $("#socketconsole").append("Connessione stabilita<br>");
 // alert("Invio al server");
  $("#socketconsole").append("Invio al server i dati<br>");
  $("#socketconsole").append(socket.readyState);
  socket.send("Sono connesso baby");
  
  //socket.send("Il mio nome è John");
};
socket.onerror = function(error) {
  //alert(`[error] ${error.message}`);
  $("#socketconsole").append("Errore "+error.message+"<br>");
  console.log(socket.readyState);
};

	function sendbutton(button) {
		console.log(socket.readyState);
	socket.send(button);
}
function testsocket() {
	console.log(socket.readyState);
socket.send("Sono il dato inviato via socket");
}
</script>
