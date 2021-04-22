##### Using this demo #####

1. Run Docker container of jaeger all-in-one 1.22

	docker run -d --name jaeger -p5775:5775/udp -p6831:6831/udp -p6832:6832/udp -p5778:5778 -p16686:16686 -p14268:14268 -p14250:14250 -p9411:9411 -p14269:14269 jaegertracing/all-in-one:1.22

	OR

	docker start jaeger (if you already have the image)

1a. pip3 install gprfcio google protobuf jaeger_client
	

2. Run node1_server.py in python3 on a second terminal to start the gRPC server

3. Run test_client.py on main terminal to send and trace the request

4. Go to http://localhost:16686 on a browser to see UI
