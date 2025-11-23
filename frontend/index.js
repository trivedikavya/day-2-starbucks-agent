document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const startScreen = document.getElementById("start-screen");
  const conversationScreen = document.getElementById("conversation-screen");
  const startConvBtn = document.getElementById("start-conv-btn");
  const micToggleBtn = document.getElementById("mic-toggle-btn");
  const statusText = document.getElementById("status-text");
  const agentAudio = document.getElementById("agent-audio");

  // Display Elements
  const dispDrink = document.getElementById("disp-drink");
  const dispSize = document.getElementById("disp-size");
  const dispMilk = document.getElementById("disp-milk");
  const dispName = document.getElementById("disp-name");
  const dispExtras = document.getElementById("disp-extras");

  let mediaRecorder;
  let audioChunks = [];
  let isRecording = false;

  // --- ORDER STATE MEMORY ---
  let currentOrderState = {
    drinkType: null,
    size: null,
    milk: null,
    extras: [],
    name: null,
    is_complete: false
  };

  // --- 1. START CONVERSATION ---
  startConvBtn.addEventListener("click", async () => {
    startScreen.classList.add("hidden");
    conversationScreen.classList.remove("hidden");
    statusText.textContent = "Connecting...";

    // Reset UI
    updateDisplay();

    try {
      const res = await axios.post("http://localhost:5000/server", {
        text: "Hi there! Welcome to Starbucks. What can I get started for you today?"
      });

      if (res.data.audioUrl) {
        playAudio(res.data.audioUrl);
      }
    } catch (error) {
      statusText.textContent = "Error connecting to barista.";
      console.error(error);
    }
  });

  // --- 2. MIC TOGGLE LOGIC ---
  micToggleBtn.addEventListener("click", async () => {
    if (!isRecording) {
      // START RECORDING
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = event => audioChunks.push(event.data);
        
        mediaRecorder.onstop = async () => {
          // USER STOPPED -> SEND TO SERVER
          statusText.textContent = "Thinking... ☕";
          micToggleBtn.innerHTML = "⏳";
          micToggleBtn.classList.remove("bg-red-500", "text-white", "pulse-ring");
          micToggleBtn.classList.add("bg-gray-200", "text-gray-400");
          micToggleBtn.disabled = true;

          const blob = new Blob(audioChunks, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append("file", blob, "recording.webm");
          formData.append("current_state", JSON.stringify(currentOrderState));

          try {
            // SEND TO BACKEND
            const res = await axios.post("http://localhost:5000/chat-with-voice", formData, {
              headers: { "Content-Type": "multipart/form-data" }
            });

            // 1. UPDATE STATE & UI
            if (res.data.updated_state) {
                currentOrderState = res.data.updated_state;
                updateDisplay(); // VISUAL UPDATE
            }

            // 2. PLAY RESPONSE
            if (res.data.audio_url) {
              playAudio(res.data.audio_url);
            }

          } catch (err) {
            console.error(err);
            statusText.textContent = "Sorry, I didn't catch that.";
            resetMicUI();
          }
        };

        mediaRecorder.start();
        isRecording = true;
        
        // UI UPDATES (Mic ON)
        statusText.textContent = "Listening...";
        micToggleBtn.innerHTML = "⏹️"; 
        micToggleBtn.classList.remove("bg-gray-200");
        micToggleBtn.classList.add("bg-red-500", "text-white", "pulse-ring");

      } catch (err) {
        alert("Microphone permission denied.");
      }

    } else {
      // STOP RECORDING
      mediaRecorder.stop();
      isRecording = false;
    }
  });

  // Helper: Update the Visual Receipt
  function updateDisplay() {
    dispDrink.textContent = currentOrderState.drinkType || "-";
    dispSize.textContent = currentOrderState.size || "-";
    dispMilk.textContent = currentOrderState.milk || "-";
    dispName.textContent = currentOrderState.name || "-";
    
    if (currentOrderState.extras && currentOrderState.extras.length > 0) {
        dispExtras.textContent = "Extras: " + currentOrderState.extras.join(", ");
    } else {
        dispExtras.textContent = "Extras: None";
    }
  }

  // Helper: Play Audio
  function playAudio(url) {
    agentAudio.src = url;
    statusText.textContent = "Speaking...";
    agentAudio.play();

    agentAudio.onended = () => {
      if (currentOrderState.is_complete) {
        statusText.textContent = "Order Placed! ✅";
        micToggleBtn.innerHTML = "🎉";
        micToggleBtn.classList.add("bg-green-100", "text-green-600");
      } else {
        resetMicUI();
      }
    };
  }

  function resetMicUI() {
    statusText.textContent = "Tap to Reply";
    micToggleBtn.disabled = false;
    micToggleBtn.classList.remove("bg-gray-400");
    micToggleBtn.classList.add("bg-gray-200", "text-gray-800");
    micToggleBtn.innerHTML = "🎙️";
  }
});