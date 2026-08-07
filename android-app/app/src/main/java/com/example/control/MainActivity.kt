package com.example.control

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.util.Log
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.setContent
import androidx.camera.core.*
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.foundation.clickable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Edit
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.filled.Delete
import androidx.compose.animation.animateColorAsState
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import okhttp3.*
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.io.IOException
import java.util.concurrent.Executors

class MainActivity : ComponentActivity() {
    @OptIn(ExperimentalMaterial3Api::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                RelayAppDashboard()
            }
        }
    }
}

data class RelayBoard(
    val id: String,
    val ipAddress: String,
    val relayNames: List<String> = listOf("Relay 1", "Relay 2", "Relay 3", "Relay 4")
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RelayAppDashboard() {
    val context = LocalContext.current

    val vibrator = remember { context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator }

    val prefs = remember { context.getSharedPreferences("RelayPrefs", Context.MODE_PRIVATE) }

    var isScanningQr by remember { mutableStateOf(false) }
    var isScanningNetwork by remember { mutableStateOf(false) }

    // UI State for the Edit Popup (Stores which board and which relay index is being edited)
    var editingRelay by remember { mutableStateOf<Pair<RelayBoard, Int>?>(null) }

    var boardToDelete by remember { mutableStateOf<RelayBoard?>(null) }

    val relayStates = remember { mutableStateMapOf<String, Boolean>() }

    val connectionStates = remember { mutableStateMapOf<String, Boolean>() }

    val activeSockets = remember { mutableStateMapOf<String, WebSocket>() }

    // 2. Upgraded Loader: Reads custom names, or defaults to "Relay X" for your older saves
    val boardList = remember {
        val savedBoards = prefs.getStringSet("saved_boards", emptySet()) ?: emptySet()
        val initialList = savedBoards.mapNotNull {
            val parts = it.split(",")
            if (parts.size >= 2) {
                // Parse custom names split by "|" or fallback to defaults
                val names = if (parts.size > 2) parts[2].split("|") else listOf(
                    "Relay 1",
                    "Relay 2",
                    "Relay 3",
                    "Relay 4"
                )
                RelayBoard(parts[0], parts[1], names)
            } else null
        }
        mutableStateListOf<RelayBoard>().apply { addAll(initialList) }
    }

    boardList.forEach { board ->
        DisposableEffect(board.ipAddress) {
            val request = Request.Builder().url("ws://${board.ipAddress}:81/").build()

            val listenerSocket = httpClient.newWebSocket(request, object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    connectionStates[board.id] = true
                    // SAVE SOCKET: Keep a live reference to reuse for sending commands
                    activeSockets[board.id] = webSocket
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    connectionStates[board.id] = false
                    activeSockets.remove(board.id)
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    connectionStates[board.id] = false
                    activeSockets.remove(board.id)
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    // --- NEW: Intercept name updates instantly ---
                    if (text.startsWith("NAMES:")) {
                        val names = text.removePrefix("NAMES:").split("|")
                        if (names.size == 4) {
                            val index = boardList.indexOfFirst { it.id == board.id }
                            if (index >= 0) {
                                boardList[index] = boardList[index].copy(relayNames = names)
                                val updatedSet = boardList.map {
                                    "${it.id},${it.ipAddress},${
                                        it.relayNames.joinToString("|")
                                    }"
                                }.toSet()
                                prefs.edit().putStringSet("saved_boards", updatedSet).apply()
                            }
                        }
                        return
                    }

                    // Original toggle/sync interpretation
                    val parts =
                        if (text.startsWith("SYNC")) text.split(":").drop(1) else listOf(text)
                    for (part in parts) {
                        if (part.contains("_")) {
                            val r = part.substringBefore("_")
                            val s = part.substringAfter("_")
                            if (r in listOf("1", "2", "3", "4")) {
                                val stateKey = "${board.id}_$r"
                                relayStates[stateKey] = (s == "ON")
                            }
                        }
                    }
                }
            })

            onDispose {
                listenerSocket.close(1000, "Dashboard closed")
                connectionStates[board.id] = false
                activeSockets.remove(board.id)
            }
        }
    }

    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.CAMERA
            ) == PackageManager.PERMISSION_GRANTED
        )
    }
    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { granted -> hasCameraPermission = granted }
    )

    // 3. Upgraded Saver: Protects custom names from being overwritten by background network scans
    val addAndSaveBoard: (RelayBoard, Boolean) -> Unit = { newBoard, isUserEdit ->
        val existingIndex = boardList.indexOfFirst { it.id == newBoard.id }
        var listChanged = false

        if (existingIndex >= 0) {
            val existingBoard = boardList[existingIndex]
            if (isUserEdit) {
                // User actively changed a name, accept the overwrite
                boardList[existingIndex] = newBoard
                listChanged = true
            } else if (existingBoard.ipAddress != newBoard.ipAddress) {
                // Background scan found a new IP. Update IP, but KEEP existing custom names!
                boardList[existingIndex] = existingBoard.copy(ipAddress = newBoard.ipAddress)
                listChanged = true
            }
        } else {
            boardList.add(newBoard)
            listChanged = true
        }

        if (listChanged) {
            // Save format: "BOARD_ID,192.168.x.x,Name1|Name2|Name3|Name4"
            val updatedSet =
                boardList.map { "${it.id},${it.ipAddress},${it.relayNames.joinToString("|")}" }
                    .toSet()
            prefs.edit().putStringSet("saved_boards", updatedSet).apply()
        }
    }

    // --- The Popup Dialog for Editing Names ---
    if (editingRelay != null) {
        val (board, index) = editingRelay!!
        var tempName by remember(editingRelay) { mutableStateOf(board.relayNames[index]) }

        AlertDialog(
            onDismissRequest = { editingRelay = null },
            title = { Text("Edit Relay Name") },
            text = {
                OutlinedTextField(
                    value = tempName,
                    onValueChange = { tempName = it },
                    singleLine = true,
                    label = { Text("New Name") }
                )
            },
            confirmButton = {
                Button(onClick = {
                    val safeName = tempName.ifBlank { "Relay ${index + 1}" }
                    val command = "SET_NAME:${index + 1}:$safeName"

                    val liveSocket = activeSockets[board.id]
                    if (liveSocket != null) {
                        // Sends instantly over the active background pipeline
                        liveSocket.send(command)
                    } else {
                        // Fallback
                        sendRelayCommand(board.ipAddress, command) { freshNames ->
                            addAndSaveBoard(board.copy(relayNames = freshNames), true)
                        }
                    }

                    editingRelay = null
                }) { Text("Save to ESP") }
            },
            dismissButton = {
                TextButton(onClick = { editingRelay = null }) { Text("Cancel") }
            }
        )
    }

    if (boardToDelete != null) {
        val board = boardToDelete!!
        AlertDialog(
            onDismissRequest = { boardToDelete = null },
            title = { Text("Delete Board") },
            text = { Text("Are you sure you want to remove '${board.id}' from your device?") },
            confirmButton = {
                Button(
                    onClick = {
                        // 1. Remove from local state
                        boardList.remove(board)

                        // 2. Save the updated list to SharedPreferences
                        val updatedSet =
                            boardList.map { "${it.id},${it.ipAddress},${it.relayNames.joinToString("|")}" }
                                .toSet()
                        prefs.edit().putStringSet("saved_boards", updatedSet).apply()

                        // 3. Close dialog
                        boardToDelete = null
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                ) { Text("Delete") }
            },
            dismissButton = {
                TextButton(onClick = { boardToDelete = null }) { Text("Cancel") }
            }
        )
    }

    DisposableEffect(isScanningNetwork) {
        if (!isScanningNetwork) return@DisposableEffect onDispose {}

        val nsdManager = context.getSystemService(Context.NSD_SERVICE) as NsdManager
        val wifiManager =
            context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val multicastLock = wifiManager.createMulticastLock("esp_relay_multicast_lock").apply {
            setReferenceCounted(true)
            acquire()
        }

        val discoveryListener = object : NsdManager.DiscoveryListener {
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                isScanningNetwork = false
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                nsdManager.stopServiceDiscovery(this)
            }

            override fun onDiscoveryStarted(serviceType: String) {}
            override fun onDiscoveryStopped(serviceType: String) {
                isScanningNetwork = false
            }

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                val uniqueResolveListener = object : NsdManager.ResolveListener {
                    override fun onResolveFailed(info: NsdServiceInfo, errorCode: Int) {}
                    override fun onServiceResolved(resolvedServiceInfo: NsdServiceInfo) {
                        val hostIp = resolvedServiceInfo.host.hostAddress ?: return
                        val hostName = resolvedServiceInfo.serviceName

                        // When we find a board, instantly ping it for its true names!
                        sendRelayCommand(hostIp, "GET_NAMES") { realNames ->
                            addAndSaveBoard(
                                RelayBoard(
                                    id = hostName,
                                    ipAddress = hostIp,
                                    relayNames = realNames
                                ), true
                            )
                        }
                    }
                }
                try {
                    nsdManager.resolveService(serviceInfo, uniqueResolveListener)
                } catch (e: Exception) {
                }
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo) {}
        }

        nsdManager.discoverServices("_ws._tcp.", NsdManager.PROTOCOL_DNS_SD, discoveryListener)

        onDispose {
            try {
                nsdManager.stopServiceDiscovery(discoveryListener)
            } catch (e: Exception) {
            }
            if (multicastLock.isHeld) multicastLock.release()
        }
    }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Damon Control",
                        fontWeight = FontWeight.ExtraBold,
                        color = MaterialTheme.colorScheme.primary
                    )
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier.padding(padding).fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
        ) {
            if (isScanningQr) {
                QRCameraScanner(
                    onQrCodeScanned = { qrData ->
                        try {
                            val json = org.json.JSONObject(qrData)
                            val name = json.getString("name")
                            val ip = json.getString("ip")

                            val customNames =
                                mutableListOf("Relay 1", "Relay 2", "Relay 3", "Relay 4")
                            if (json.has("names")) {
                                val namesObj = json.getJSONObject("names")
                                for (i in 1..4) {
                                    if (namesObj.has(i.toString())) {
                                        customNames[i - 1] = namesObj.getString(i.toString())
                                    }
                                }
                            }
                            addAndSaveBoard(
                                RelayBoard(
                                    id = name,
                                    ipAddress = ip,
                                    relayNames = customNames
                                ), false
                            )

                        } catch (e: Exception) {
                            val parts = qrData.split(",")
                            if (parts.size >= 2) {
                                addAndSaveBoard(
                                    RelayBoard(id = parts[0], ipAddress = parts[1]),
                                    false
                                )
                            }
                        }
                        isScanningQr = false
                    },
                    onClose = { isScanningQr = false }
                )
            } else {
                Column(modifier = Modifier.fillMaxSize()) {
                    // --- TOP ACTION BUTTONS ---
                    Row(
                        modifier = Modifier.fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 8.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        OutlinedButton(
                            onClick = {
                                if (hasCameraPermission) isScanningQr = true
                                else launcher.launch(Manifest.permission.CAMERA)
                            },
                            shape = RoundedCornerShape(50),
                            modifier = Modifier.weight(1f).height(50.dp)
                        ) {
                            Text("Scan QR", fontWeight = FontWeight.Bold)
                        }

                        Button(
                            onClick = { isScanningNetwork = !isScanningNetwork },
                            shape = RoundedCornerShape(50),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (isScanningNetwork) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary
                            ),
                            modifier = Modifier.weight(1f).height(50.dp)
                        ) {
                            Text(
                                if (isScanningNetwork) "Stop Scan" else "Network Scan",
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    if (isScanningNetwork) {
                        LinearProgressIndicator(
                            modifier = Modifier.fillMaxWidth()
                                .padding(horizontal = 24.dp, vertical = 8.dp)
                                .clip(RoundedCornerShape(50))
                        )
                        Text(
                            text = "Searching for boards on Wi-Fi...",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.align(Alignment.CenterHorizontally)
                        )
                    }

                    // --- BOARD LIST ---
                    if (boardList.isEmpty()) {
                        Box(
                            modifier = Modifier.weight(1f).fillMaxWidth(),
                            contentAlignment = Alignment.Center
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Icon(
                                    imageVector = Icons.Default.Edit,
                                    contentDescription = null,
                                    modifier = Modifier.size(64.dp),
                                    tint = MaterialTheme.colorScheme.surfaceVariant
                                )
                                Spacer(modifier = Modifier.height(16.dp))
                                Text(
                                    text = "No boards added yet",
                                    style = MaterialTheme.typography.titleMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier.weight(1f).fillMaxSize(),
                            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                            verticalArrangement = Arrangement.spacedBy(16.dp)
                        ) {
                            items(boardList) { board ->
                                ElevatedCard(
                                    shape = RoundedCornerShape(24.dp),
                                    elevation = CardDefaults.elevatedCardElevation(defaultElevation = 2.dp),
                                    colors = CardDefaults.elevatedCardColors(
                                        containerColor = MaterialTheme.colorScheme.surface
                                    ),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Column(modifier = Modifier.padding(20.dp)) {
                                        val isConnected = connectionStates[board.id] ?: false

                                        // HEADER: Board Name, IP, Status, and Delete
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.SpaceBetween,
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Column(modifier = Modifier.weight(1f)) {
                                                Text(
                                                    text = board.id.uppercase(),
                                                    style = MaterialTheme.typography.titleLarge,
                                                    fontWeight = FontWeight.Black,
                                                    color = MaterialTheme.colorScheme.onSurface
                                                )
                                                Text(
                                                    text = board.ipAddress,
                                                    style = MaterialTheme.typography.labelLarge,
                                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                                )
                                            }

                                            // --- STATUS CHIP & DELETE BUTTON ---
                                            Row(
                                                verticalAlignment = Alignment.CenterVertically,
                                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                                            ) {
                                                val statusColor by animateColorAsState(
                                                    targetValue = if (isConnected) Color(0xFF00C853) else MaterialTheme.colorScheme.error,
                                                    label = "statusColor"
                                                )

                                                // Beautiful Status Chip
                                                Surface(
                                                    shape = RoundedCornerShape(50),
                                                    color = statusColor.copy(alpha = 0.1f),
                                                    border = androidx.compose.foundation.BorderStroke(
                                                        1.dp,
                                                        statusColor.copy(alpha = 0.3f)
                                                    )
                                                ) {
                                                    Row(
                                                        modifier = Modifier.padding(
                                                            horizontal = 10.dp,
                                                            vertical = 6.dp
                                                        ),
                                                        verticalAlignment = Alignment.CenterVertically,
                                                        horizontalArrangement = Arrangement.spacedBy(
                                                            6.dp
                                                        )
                                                    ) {
                                                        Box(
                                                            modifier = Modifier.size(8.dp)
                                                                .clip(CircleShape)
                                                                .background(statusColor)
                                                        )
                                                        Text(
                                                            text = if (isConnected) "ONLINE" else "OFFLINE",
                                                            color = statusColor,
                                                            style = MaterialTheme.typography.labelSmall,
                                                            fontWeight = FontWeight.Bold
                                                        )
                                                    }
                                                }

                                                // Delete Button
                                                IconButton(
                                                    onClick = { boardToDelete = board },
                                                    modifier = Modifier.size(32.dp)
                                                ) {
                                                    Icon(
                                                        imageVector = Icons.Default.Delete,
                                                        contentDescription = "Delete Board",
                                                        tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(
                                                            alpha = 0.6f
                                                        )
                                                    )
                                                }
                                            }
                                        }

                                        Spacer(modifier = Modifier.height(20.dp))

                                        // RELAY LIST: Grouped in bubbles
                                        for (i in 1..4) {
                                            val stateKey = "${board.id}_$i"
                                            val isChecked = relayStates[stateKey] ?: false

                                            Surface(
                                                shape = RoundedCornerShape(16.dp),
                                                color = MaterialTheme.colorScheme.surfaceVariant.copy(
                                                    alpha = 0.4f
                                                ),
                                                modifier = Modifier.fillMaxWidth()
                                                    .padding(vertical = 4.dp)
                                            ) {
                                                Row(
                                                    modifier = Modifier.fillMaxWidth().padding(
                                                        horizontal = 16.dp,
                                                        vertical = 8.dp
                                                    ),
                                                    horizontalArrangement = Arrangement.SpaceBetween,
                                                    verticalAlignment = Alignment.CenterVertically
                                                ) {
                                                    // Clickable Custom Name
                                                    Row(
                                                        verticalAlignment = Alignment.CenterVertically,
                                                        modifier = Modifier
                                                            .clip(RoundedCornerShape(8.dp))
                                                            .clickable {
                                                                editingRelay = board to (i - 1)
                                                            }
                                                            .padding(
                                                                vertical = 8.dp,
                                                                horizontal = 4.dp
                                                            )
                                                    ) {
                                                        Icon(
                                                            imageVector = Icons.Default.Edit,
                                                            contentDescription = "Edit Name",
                                                            modifier = Modifier.size(14.dp),
                                                            tint = MaterialTheme.colorScheme.primary
                                                        )
                                                        Spacer(modifier = Modifier.width(8.dp))
                                                        Text(
                                                            text = board.relayNames[i - 1],
                                                            style = MaterialTheme.typography.titleMedium,
                                                            fontWeight = FontWeight.Medium
                                                        )
                                                    }

                                                    // --- Wrapped Toggle Switch ---
                                                    Box(contentAlignment = Alignment.Center) {
                                                        Switch(
                                                            checked = isChecked,
                                                            enabled = isConnected,
                                                            onCheckedChange = { checked ->
                                                                relayStates[stateKey] = checked
                                                                val command = if (checked) "${i}_ON" else "${i}_OFF"

                                                                val liveSocket = activeSockets[board.id]
                                                                if (liveSocket != null) {
                                                                    liveSocket.send(command)
                                                                } else {
                                                                    sendRelayCommand(board.ipAddress, command)
                                                                }
                                                            }
                                                        )

                                                        // Transparent overlay that intercepts taps ONLY when disconnected
                                                        if (!isConnected) {
                                                            Box(
                                                                modifier = Modifier
                                                                    .matchParentSize()
                                                                    .clickable(
                                                                        interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() },
                                                                        indication = null // Removes the ripple effect so it feels completely solid/disabled
                                                                    ) {
                                                                        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                                                                            vibrator.vibrate(
                                                                                VibrationEffect.createOneShot(
                                                                                    50,
                                                                                    VibrationEffect.DEFAULT_AMPLITUDE
                                                                                )
                                                                            )
                                                                        } else {
                                                                            @Suppress("DEPRECATION")
                                                                            vibrator.vibrate(50)
                                                                        }
                                                                    }
                                                            )
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@SuppressLint("UnsafeOptInUsageError")
@Composable
fun QRCameraScanner(onQrCodeScanned: (String) -> Unit, onClose: () -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val cameraExecutor = remember { Executors.newSingleThreadExecutor() }
    val previewView = remember { PreviewView(context) }

    Box(modifier = Modifier.fillMaxSize()) {
        AndroidView(
            factory = { previewView },
            modifier = Modifier.fillMaxSize()
        ) { view ->
            val cameraProviderFuture = androidx.camera.lifecycle.ProcessCameraProvider.getInstance(context)
            cameraProviderFuture.addListener({
                val cameraProvider = cameraProviderFuture.get()
                val preview = Preview.Builder().build().also {
                    it.setSurfaceProvider(view.surfaceProvider)
                }

                val imageAnalyzer = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                    .also { analyzer ->
                        analyzer.setAnalyzer(cameraExecutor) { imageProxy ->
                            val mediaImage = imageProxy.image
                            if (mediaImage != null) {
                                val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
                                val scanner = BarcodeScanning.getClient()
                                scanner.process(image)
                                    .addOnSuccessListener { barcodes ->
                                        for (barcode in barcodes) {
                                            barcode.rawValue?.let { qrValue ->
                                                onQrCodeScanned(qrValue)
                                            }
                                        }
                                    }
                                    .addOnCompleteListener { imageProxy.close() }
                            } else {
                                imageProxy.close()
                            }
                        }
                    }

                try {
                    cameraProvider.unbindAll()
                    cameraProvider.bindToLifecycle(
                        lifecycleOwner,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        imageAnalyzer
                    )
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }, ContextCompat.getMainExecutor(context))
        }

        Button(onClick = onClose, modifier = Modifier.padding(16.dp)) {
            Text("Cancel")
        }
    }
}

private val httpClient = OkHttpClient()
fun sendRelayCommand(ipAddress: String, command: String, onNamesReceived: ((List<String>) -> Unit)? = null) {
    val request = Request.Builder().url("ws://$ipAddress:81/").build()

    httpClient.newWebSocket(request, object : WebSocketListener() {
        override fun onMessage(webSocket: WebSocket, text: String) {
            Log.d("WebSocket", "Received: $text")

            if (text.startsWith("SYNC")) {
                if (command.isNotEmpty()) webSocket.send(command)
            }
            else if (text.startsWith("NAMES:")) {
                val names = text.removePrefix("NAMES:").split("|")
                if (names.size == 4) {
                    // Send the names back to the UI on the main thread
                    Handler(Looper.getMainLooper()).post { onNamesReceived?.invoke(names) }
                }

                if (command == "GET_NAMES" || command.startsWith("SET_NAME")) {
                    webSocket.close(1000, "Task Complete")
                }
            }
            else if (text == command) {
                webSocket.close(1000, "Relay Flipped")
            }
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            Log.e("WebSocket", "Failed to reach $ipAddress", t)
        }
    })
}