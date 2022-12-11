# cloud-rc-car
RC Car Controlled via Cloud 4g connection with Camera Streaming
<br>
What you need for build it<br>
<br>
1- Rc Car to disassemble<br>
2- Raspberry Pi to be mounted on the rc car<br>
3- Arduino<br>
4- Motorshield<br>
5- Xbox Joypad 
<br>
<br>
<br>
We use 3 script for Control the RC Car and 3 script for stream the camera<br>
<br>
<strong>For Control RC Car</strong><br>
1- Client (tablet/smartphone or pc) - Webpage with Socket Client<br>
2- Server (raspberry pi debian linux) - WebSocket Server in NodeJs, recive data from web and send on serial port<br>
3- Firmware for Arduino motorshield - Recive data on serial port and activate pin<br>
<br>
<strong>For Stream WebCamera</strong><br>
We use <br>
1- Local WebPage for show the content of Webcam from StreamServer Script<br>
2- Stream Server Script Daemon<br>
3- FFMPEG for get video from webcam and send to Stream Server Daemon<br>
<br>
<br>
All Daemon boot at startup and send ip to Email - we need only connect on webpage and play with RC Car, in remote location

