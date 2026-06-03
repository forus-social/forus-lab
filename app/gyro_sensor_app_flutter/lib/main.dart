import 'package:flutter/material.dart'; //for the ui
import 'dart:async'; //for the timer
import 'dart:convert';  //for some json stuff
import 'dart:io'; //for exporting json
import 'dart:math'; //only using random from this to generate the session ID
import 'package:sensors_plus/sensors_plus.dart'; //sensors
import 'package:fl_chart/fl_chart.dart'; //charts
import 'package:path_provider/path_provider.dart'; //for adding files (temp) to the deivce
import 'package:share_plus/share_plus.dart'; //for sharing
import 'package:http/http.dart' as http; //for posting readings to the laptop api

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) { //this is just like the top bar, the root of the app
    return MaterialApp(
      title: 'Sensor Data App',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color.fromARGB(255, 103, 38, 255)),
      ),
      home: const MyHomePage(title: 'Sensor Demo'),
    );
  }
}

class CombinedSensorSample { //this is a class to store each sample from the sensor as well as a timestamp
  final int t;
  final double ax, ay, az;
  final double gx, gy, gz;

  CombinedSensorSample(this.t, this.ax, this.ay, this.az, this.gx, this.gy, this.gz);

  Map<String, dynamic> toJson() => {
        't': t,
        'ax': double.parse(ax.toStringAsFixed(4)),
        'ay': double.parse(ay.toStringAsFixed(4)),
        'az': double.parse(az.toStringAsFixed(4)),
        'gx': double.parse(gx.toStringAsFixed(4)),
        'gy': double.parse(gy.toStringAsFixed(4)),
        'gz': double.parse(gz.toStringAsFixed(4)),
      };
}

class MyHomePage extends StatefulWidget { //this is another shell part of the app that i dont really understand, has something to do with the main page
  const MyHomePage({super.key, required this.title});
  final String title;

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  final TextEditingController _deviceIdController = TextEditingController(text: 'phoneA'); //this is for the textbox
  final TextEditingController _serverUrlController = TextEditingController(text: 'http://192.168.1.100:8000'); //change to laptop LAN IP
  String _currentSessionId = '';

  int _selectedTime = 10;         //default states
  int _timeLeft = 0;
  bool _isRecording = false;
  bool _isWaiting = false;        // true while polling for pairing result
  Timer? _timer;

  final List<CombinedSensorSample> _recordedSamples = [];
  DateTime? _startTime;

  StreamSubscription<GyroscopeEvent>? _gyroSubscription;
  StreamSubscription<AccelerometerEvent>? _accelSubscription;

  double _latestGx = 0.0;
  double _latestGy = 0.0;
  double _latestGz = 0.0;

  String _generateSessionId() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    final random = Random();
    return String.fromCharCodes(Iterable.generate(
      6, (_) => chars.codeUnitAt(random.nextInt(chars.length))
    ));
  }

  void _startRecording() {                        //everything here occurs when the recording is started
    if (_deviceIdController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a Device ID first!')),
      );
      return;
    }

    _timer?.cancel();
    _gyroSubscription?.cancel();
    _accelSubscription?.cancel();

    setState(() {     //happens when recording is started
      _isRecording = true;
      _isWaiting = false;
      _timeLeft = _selectedTime;
      _recordedSamples.clear();
      _startTime = DateTime.now();
      _currentSessionId = _generateSessionId();
    });

    _gyroSubscription = gyroscopeEventStream().listen((GyroscopeEvent event) {    //these subscriptions use streams which im not super familer with, seems to just constantly read data
      _latestGx = event.x;
      _latestGy = event.y;
      _latestGz = event.z;
    });

    _accelSubscription = accelerometerEventStream().listen((AccelerometerEvent event) {
      _recordedSamples.add(CombinedSensorSample(
        DateTime.now().millisecondsSinceEpoch,
        event.x, event.y, event.z,
        _latestGx, _latestGy, _latestGz
      ));
      setState(() {});
    });

    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {   //count down the timer
      setState(() {
        if (_timeLeft > 0) {
          _timeLeft--;
        } else {      //fixes the state when the timer is up
          _isRecording = false;
          timer.cancel();
          _gyroSubscription?.cancel();
          _accelSubscription?.cancel();
          _uploadAndPoll();  // auto-upload and wait for result
        }
      });
    });
  }

  // Upload the reading then poll for the pairing result.
  Future<void> _uploadAndPoll() async {
    final ok = await _doUpload();
    if (!ok || !mounted) return;

    setState(() => _isWaiting = true);

    final deviceId = _deviceIdController.text.trim();
    final base = _serverUrlController.text.trim();

    for (int i = 0; i < 8; i++) {
      await Future.delayed(const Duration(seconds: 2));
      if (!mounted) return;
      try {
        final resp = await http
            .get(Uri.parse('$base/result/$deviceId'))
            .timeout(const Duration(seconds: 5));
        final body = jsonDecode(resp.body) as Map<String, dynamic>;
        if (body['status'] == 'ready') {
          if (!mounted) return;
          setState(() => _isWaiting = false);
          _showResultDialog(body);
          return;
        }
      } catch (_) {}
    }

    if (!mounted) return;
    setState(() => _isWaiting = false);
    _showResultDialog({'status': 'timeout'});
  }

  // Does the HTTP POST. Returns true on success, shows SnackBar on failure.
  Future<bool> _doUpload() async {
    final url = _serverUrlController.text.trim();
    if (url.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Enter the server URL first.')),
        );
      }
      return false;
    }

    final Map<String, dynamic> payload = {
      "device_id": _deviceIdController.text.trim(),
      "session_id": _currentSessionId,
      "samples": _recordedSamples.map((s) => s.toJson()).toList(),
    };

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Uploading...'), duration: Duration(seconds: 2)),
      );
    }

    try {
      final response = await http.post(
        Uri.parse('$url/readings'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(payload),
      ).timeout(const Duration(seconds: 10));
      return response.statusCode == 200;
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e')),
        );
      }
      return false;
    }
  }

  void _showResultDialog(Map<String, dynamic> result) {
    final isTimeout = result['status'] == 'timeout';
    final matched   = result['match'] == true;

    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(
          isTimeout ? 'No partner found'
          : matched ? '✓ Match!'
                    : '✗ No match',
          style: TextStyle(
            color: isTimeout ? Colors.orange
                 : matched   ? Colors.green
                             : Colors.red,
            fontWeight: FontWeight.bold,
            fontSize: 22,
          ),
        ),
        content: isTimeout
            ? const Text('No second device uploaded within the time window.')
            : Text(
                'Accel:   ${(result['accel_score'] as double).toStringAsFixed(3)}\n'
                'Gyro:    ${(result['gyro_score']  as double).toStringAsFixed(3)}\n'
                'Partner: ${result['partner']}',
                style: const TextStyle(fontSize: 16),
              ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  Future<void> _previewAndShare() async {   //all this is to do with the exporting of the JSON, not rlly pertinant to the final app so dont worry about it
    Map<String, dynamic> finalPayload = {
      "device_id": _deviceIdController.text.trim(),
      "session_id": _currentSessionId,
      "samples": _recordedSamples.map((sample) => sample.toJson()).toList(),
    };

    String jsonString = const JsonEncoder.withIndent('  ').convert(finalPayload);

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('JSON Preview'),
          content: SingleChildScrollView(
            child: Text(jsonString, style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Close'),
            ),
            ElevatedButton.icon(
              icon: const Icon(Icons.share),
              label: const Text('Export File'),
              onPressed: () async {
                try {
                  final size = MediaQuery.of(context).size;

                  Navigator.of(context).pop();

                  final directory = await getTemporaryDirectory();
                  final file = File('${directory.path}/sensor_$_currentSessionId.json');
                  await file.writeAsString(jsonString);

                  await Share.shareXFiles(
                    [XFile(file.path)],
                    text: 'Sensor Data: $_currentSessionId',

                    sharePositionOrigin: Rect.fromLTWH(0, 0, size.width, size.height / 2),
                  );

                } catch (e) {
                  print("🚨 EXPORT ERROR: $e");   //I was getting a weird error when tryna get the IOS file share dialog to pop up so this is useful for debugging
                                                  // itll be printed in the debug of your ide
                }
              },
            ),
          ],
        );
      },
    );
  }

  @override   // good practice to close all streams, even though we did it when the timer finished
  void dispose() {
    _timer?.cancel();
    _gyroSubscription?.cancel();
    _accelSubscription?.cancel();
    _deviceIdController.dispose();
    _serverUrlController.dispose();
    super.dispose();
  }

  Widget _buildSensorChart(bool isAccel) {    //this is for charting, again not super pertinant
    if (_recordedSamples.isEmpty) return const SizedBox(height: 150, child: Center(child: Text('No data yet')));

    List<FlSpot> spotsX = [];
    List<FlSpot> spotsY = [];
    List<FlSpot> spotsZ = [];

    for (var sample in _recordedSamples) {
      if (_startTime == null) continue;

      DateTime sampleTime = DateTime.fromMillisecondsSinceEpoch(sample.t);
      double timeSeconds = sampleTime.difference(_startTime!).inMilliseconds / 1000.0;

      if (isAccel) {
        spotsX.add(FlSpot(timeSeconds, sample.ax));
        spotsY.add(FlSpot(timeSeconds, sample.ay));
        spotsZ.add(FlSpot(timeSeconds, sample.az));
      } else {
        spotsX.add(FlSpot(timeSeconds, sample.gx));
        spotsY.add(FlSpot(timeSeconds, sample.gy));
        spotsZ.add(FlSpot(timeSeconds, sample.gz));
      }
    }

    return SizedBox(
      height: 150,
      width: double.infinity,
      child: LineChart(
        LineChartData(
          titlesData: const FlTitlesData(show: false),
          borderData: FlBorderData(show: true, border: Border.all(color: Colors.grey.shade300)),
          gridData: const FlGridData(show: false),
          lineBarsData: [
            LineChartBarData(spots: spotsX, color: Colors.red, isCurved: true, dotData: const FlDotData(show: false)),
            LineChartBarData(spots: spotsY, color: Colors.green, isCurved: true, dotData: const FlDotData(show: false)),
            LineChartBarData(spots: spotsZ, color: Colors.blue, isCurved: true, dotData: const FlDotData(show: false)),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {  //below is all the UI aspects of the app
    final bool busy = _isRecording || _isWaiting;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        title: Text(widget.title),
      ),
      body: GestureDetector(
        onTap: () => FocusScope.of(context).unfocus(),
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [

                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20.0),
                  child: TextField(
                    controller: _serverUrlController,
                    enabled: !busy,
                    keyboardType: TextInputType.url,
                    autocorrect: false,
                    decoration: const InputDecoration(
                      labelText: 'Server URL (e.g. http://192.168.1.100:8000)',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.cloud_upload),
                    ),
                  ),
                ),

                const SizedBox(height: 12),

                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20.0),
                  child: TextField(                                         //this is for the deivce id
                    controller: _deviceIdController,
                    enabled: !busy,
                    decoration: const InputDecoration(
                      labelText: 'Device ID',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.phone_android),
                    ),
                  ),
                ),

                const SizedBox(height: 20),

                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Text('Record for: ', style: TextStyle(fontSize: 18)),   //this is the duration drop down menu
                    const SizedBox(width: 10),
                    DropdownButton<int>(
                      value: _selectedTime,
                      onChanged: busy ? null : (int? newValue) {
                        setState(() {
                          if (newValue != null) _selectedTime = newValue;
                        });
                      },
                      items: const [        //here you can change the duration options, make sure to change both the value and the display text
                        DropdownMenuItem(value: 5, child: Text('5 Seconds')),
                        DropdownMenuItem(value: 10, child: Text('10 Seconds')),
                        DropdownMenuItem(value: 30, child: Text('30 Seconds')),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  _isWaiting    ? 'Waiting for partner...'
                  : _isRecording ? 'Time left: $_timeLeft s'
                                 : 'Ready to record',
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 10),

                if (_isWaiting)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 8.0),
                    child: CircularProgressIndicator(),
                  ),

                ElevatedButton(
                  onPressed: busy ? null : _startRecording,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.deepPurple,
                    foregroundColor: Colors.white,
                    minimumSize: const Size(200, 50),
                  ),
                  child: Text(
                    _isRecording ? 'Recording...' : 'Start Recording',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
                const SizedBox(height: 10),

                if (_recordedSamples.isNotEmpty && !busy) ...[
                  ElevatedButton.icon(
                    icon: const Icon(Icons.cloud_upload),
                    label: const Text('Upload to Server'),
                    onPressed: _uploadAndPoll,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green.shade700,
                      foregroundColor: Colors.white,
                      minimumSize: const Size(200, 50),
                    ),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    icon: const Icon(Icons.code),
                    label: const Text('Preview & Export JSON'),
                    onPressed: _previewAndShare,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.deepPurple,
                      side: const BorderSide(color: Colors.deepPurple),
                      minimumSize: const Size(200, 50),
                    ),
                  ),
                ],

                const SizedBox(height: 20),//these are the graphs

                const Text('Accelerometer', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                const Text('X: Red | Y: Green | Z: Blue', style: TextStyle(fontSize: 12, color: Colors.grey)),
                _buildSensorChart(true),

                const SizedBox(height: 20),

                const Text('Gyroscope', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                const Text('X: Red | Y: Green | Z: Blue', style: TextStyle(fontSize: 12, color: Colors.grey)),
                _buildSensorChart(false),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
