(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  const page = location.pathname.split("/").pop() || "index.html";

  async function api(path, options = {}) {
    let response;
    try {
      response = await fetch(path, {
        headers: {"Content-Type": "application/json"},
        ...options,
      });
    } catch (_) {
      throw new Error("Cannot reach the ExamNet web API. Start app/web_api.py and open the site from that server.");
    }
    const raw = await response.text();
    let body;
    try {
      body = raw ? JSON.parse(raw) : {};
    } catch (_) {
      throw new Error("The web API returned an unexpected response. Start app/web_api.py and open its address.");
    }
    if (!response.ok) throw new Error(body.error || "The request failed.");
    return body;
  }

  const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));

  function initLogin() {
    const form = $("loginForm");
    if (!form) return;
    const error = $("loginError");
    const status = $("connectionStatus");

    api("/api/health").then(() => {
      status.innerHTML = '<span class="status-dot"></span> Web API is reachable';
    }).catch(() => {
      status.innerHTML = '<span class="status-dot offline"></span> Web API unavailable';
    });

    form.addEventListener("input", () => error.classList.add("hidden"));
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const name = $("candidateName").value.trim();
      const candidateId = $("candidateId").value.trim();
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      button.textContent = "Connecting to exam server…";
      error.classList.add("hidden");

      try {
        const session = await api("/api/sessions", {
          method: "POST",
          body: JSON.stringify({name, candidate_id: candidateId}),
        });
        sessionStorage.setItem("examnetSession", JSON.stringify(session));
        location.href = "exam.html";
      } catch (requestError) {
        error.textContent = requestError.message;
        error.classList.remove("hidden");
        button.disabled = false;
        button.innerHTML = 'Continue to exam <span aria-hidden="true">→</span>';
      }
    });
  }

  function initExam() {
    let session;
    try {
      session = JSON.parse(sessionStorage.getItem("examnetSession") || "null");
    } catch (_) {
      session = null;
    }
    if (!session || !session.session_id || !session.question) {
      location.href = "index.html";
      return;
    }

    const progressKey = `examnetProgress:${session.session_id}`;
    let saved;
    try {
      saved = JSON.parse(sessionStorage.getItem(progressKey) || "null");
    } catch (_) {
      saved = null;
    }

    const questions = Array.isArray(saved?.questions) && saved.questions.length
      ? saved.questions : [session.question];
    const answers = Array.isArray(saved?.answers) ? saved.answers : [];
    const marked = Array.isArray(saved?.marked) ? saved.marked : [];
    let current = Math.min(Number(saved?.current) || 0, questions.length - 1);
    let selected = saved?.selected || null;
    let busy = false;
    let finished = false;
    let deadline = Number(saved?.deadline) || Date.now() +
      (Number(session.question.time_remaining ?? session.duration) || 120) * 1000;

    $("candidateChip").textContent = session.candidate || "Candidate";

    function saveProgress() {
      sessionStorage.setItem(progressKey, JSON.stringify({
        questions, answers, marked, current, selected, deadline,
      }));
    }

    function showToast(message) {
      const toast = $("toast");
      toast.textContent = message;
      toast.classList.add("show");
      clearTimeout(showToast.timer);
      showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2600);
    }

    function updateTimer() {
      const seconds = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      const minutes = String(Math.floor(seconds / 60)).padStart(2, "0");
      const remainder = String(seconds % 60).padStart(2, "0");
      $("timer").textContent = `${minutes}:${remainder}`;
      $("timer").classList.toggle("timer-warning", seconds > 0 && seconds <= 30);
      return seconds;
    }

    function render() {
      const question = questions[current];
      if (!question) return;
      if (answers[current]) selected = answers[current];

      $("questionNumber").textContent = `QUESTION ${String(question.number).padStart(2, "0")}`;
      $("questionText").textContent = question.question;
      $("reviewPill").classList.toggle("hidden", !marked[current]);
      $("reviewBtn").classList.toggle("active", !!marked[current]);
      $("reviewBtn").setAttribute("aria-pressed", String(!!marked[current]));
      $("reviewBtn").querySelector("span:last-child").textContent = marked[current]
        ? "Remove review mark" : "Mark for review";

      const options = $("options");
      options.innerHTML = "";
      const legend = document.createElement("legend");
      legend.className = "sr-only";
      legend.textContent = "Choose one answer";
      options.appendChild(legend);

      question.options.forEach((option, index) => {
        const letter = String.fromCharCode(65 + index);
        const label = document.createElement("label");
        label.className = "option" + (selected === letter ? " selected" : "") +
          (answers[current] || busy ? " locked" : "");
        label.innerHTML = `<input type="radio" name="answer" value="${letter}" ${selected === letter ? "checked" : ""} ${answers[current] || busy ? "disabled" : ""}>` +
          `<span class="option-letter" aria-hidden="true">${letter}</span><span class="option-text"></span>`;
        label.querySelector(".option-text").textContent = option;
        label.querySelector("input").addEventListener("change", () => {
          selected = letter;
          saveProgress();
          render();
        });
        options.appendChild(label);
      });

      $("prevBtn").disabled = current === 0 || busy;
      const lastKnown = current === Number(question.total) - 1;
      $("nextBtn").textContent = busy ? "Sending answer…" : answers[current]
        ? (lastKnown ? "Exam complete" : "Next question →")
        : (lastKnown ? "Submit final answer →" : "Submit answer & continue →");
      const canAdvance = !!answers[current] && current < questions.length - 1;
      $("nextBtn").disabled = finished || busy || (!!answers[current] && !canAdvance);
      $("examStatus").textContent = busy
        ? "Sending your answer to the exam server…"
        : answers[current]
          ? "Answer recorded by the exam server. Use the palette to review visited questions."
          : "Choose one answer, then submit it to continue.";

      const answered = answers.filter(Boolean).length;
      const review = marked.filter(Boolean).length;
      $("progressText").textContent = `Question ${question.number} of ${question.total}`;
      $("answeredText").textContent = `${answered} of ${question.total} answered`;
      $("progressBar").style.width = `${answered / question.total * 100}%`;
      $("progressBar").parentElement.setAttribute("aria-valuenow", String(answered));
      $("progressBar").parentElement.setAttribute("aria-valuemax", String(question.total));
      $("legendAnswered").textContent = answers.filter((answer, i) => answer && !marked[i]).length;
      $("legendUnanswered").textContent = question.total - answered - marked.filter((value, i) => value && !answers[i]).length;
      $("legendReview").textContent = marked.filter((value, i) => value && !answers[i]).length;
      $("legendAnsweredReview").textContent = answers.filter((answer, i) => answer && marked[i]).length;

      const palette = $("palette");
      palette.innerHTML = "";
      questions.forEach((item, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "palette-btn";
        button.textContent = item.number;
        button.setAttribute("aria-current", index === current ? "step" : "false");
        if (index === current) button.classList.add("current");
        if (answers[index] && marked[index]) button.classList.add("answered-review");
        else if (answers[index]) button.classList.add("answered");
        else if (marked[index]) button.classList.add("review");
        button.title = `Question ${item.number}${answers[index] ? ": answered" : ": not answered"}${marked[index] ? ", marked for review" : ""}`;
        button.addEventListener("click", () => {
          current = index;
          selected = answers[index] || null;
          saveProgress();
          render();
        });
        palette.appendChild(button);
      });
      if (review) $("reviewBtn").setAttribute("aria-label", `${review} question(s) marked for review`);
      else $("reviewBtn").removeAttribute("aria-label");
      updateTimer();
      saveProgress();
    }

    $("reviewBtn").addEventListener("click", () => {
      marked[current] = !marked[current];
      saveProgress();
      render();
      showToast(marked[current] ? "Question marked for review" : "Review mark removed");
    });

    $("prevBtn").addEventListener("click", () => {
      if (current > 0 && !busy) {
        current--;
        selected = answers[current] || null;
        render();
      }
    });

    $("nextBtn").addEventListener("click", async () => {
      if (finished || busy) return;
      if (answers[current] && current < questions.length - 1) {
        current++;
        selected = answers[current] || null;
        render();
        return;
      }
      if (answers[current]) return;
      if (!selected) {
        showToast("Select an answer before continuing.");
        return;
      }
      busy = true;
      answers[current] = selected;
      render();
      try {
        const result = await api(`/api/sessions/${session.session_id}/answer`, {
          method: "POST",
          body: JSON.stringify({answer: selected}),
        });
        if (result.result) {
          showResult(result.result);
          return;
        }
        questions.push(result.question);
        current = questions.length - 1;
        selected = null;
        deadline = Date.now() + Math.max(0, Number(result.question.time_remaining) || 0) * 1000;
        busy = false;
        render();
      } catch (requestError) {
        answers[current] = null;
        busy = false;
        showToast(requestError.message);
        render();
      }
    });

    $("logoutBtn").addEventListener("click", async () => {
      try {
        await api(`/api/sessions/${session.session_id}`, {method: "DELETE"});
      } catch (_) {
        // Local session state still needs to be cleared if the bridge is down.
      }
      sessionStorage.removeItem("examnetSession");
      sessionStorage.removeItem(progressKey);
      location.href = "index.html";
    });

    function showResult(result) {
      finished = true;
      sessionStorage.removeItem("examnetSession");
      sessionStorage.removeItem(progressKey);
      const total = Number(result.total) || questions.length;
      document.body.innerHTML = `<main class="result-shell"><section class="result-card"><div class="brand"><span class="brand-mark">E</span><span>ExamNet <small>ONLINE EXAMINATION</small></span></div><div class="result-icon" aria-hidden="true">✓</div><div class="eyebrow">EXAM SUBMITTED</div><h1>Thank you, ${escapeHtml(result.student || session.candidate)}.</h1><p class="muted">Your result was calculated by the exam server.</p><div class="score-box"><small>SERVER RESULT</small><strong>${Number(result.score) || 0} / ${total}</strong><span>${Number(result.percentage) || 0}% correct</span></div><p class="tiny">Candidate ID ${escapeHtml(session.candidate_id || "")} is a demo label and is not authenticated by the server.</p><a class="btn primary full result-link" href="index.html">Return to login</a></section></main>`;
    }

    async function finishAtDeadline() {
      if (finished || busy) return;
      busy = true;
      $("examStatus").textContent = "Time expired. Retrieving your result from the exam server…";
      $("nextBtn").disabled = true;
      try {
        const result = await api(`/api/sessions/${session.session_id}/finish`, {method: "POST"});
        if (result.result) showResult(result.result);
      } catch (requestError) {
        busy = false;
        $("examStatus").textContent = "Could not retrieve the timed result. Check the server connection, then refresh or contact the exam administrator.";
        showToast(requestError.message);
      }
    }

    let warnedAtDeadline = false;
    let finishRetryAt = 0;
    updateTimer();
    window.setInterval(() => {
      const remaining = updateTimer();
      if (!warnedAtDeadline && remaining === 0) {
        warnedAtDeadline = true;
        showToast("Time is up. Retrieving your result…");
      }
      if (warnedAtDeadline && !busy && !finished && Date.now() >= finishRetryAt) {
        finishRetryAt = Date.now() + 5000;
        finishAtDeadline();
      }
    }, 1000);
    render();
  }

  if (page === "index.html" || page === "") initLogin();
  else if (page === "exam.html") initExam();
})();
