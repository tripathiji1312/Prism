document.addEventListener("DOMContentLoaded", () => {
    // --- ELEMENTS ---
    const dealerCards = document.getElementById("dealer-cards");
    const playerCards = document.getElementById("player-cards");
    const messageEl = document.getElementById("game-message");
    const playerScoreEl = document.getElementById("player-score");
    const dealerScoreEl = document.getElementById("dealer-score");
    
    const btnHit = document.getElementById("btn-hit");
    const btnStand = document.getElementById("btn-stand");
    const btnDeal = document.getElementById("btn-deal");

    // --- GAME STATE ---
    let deck = [];
    let playerHand = [];
    let dealerHand = [];
    let gameOver = false;

    // --- UTILITIES ---
    const suits = ["♠", "♥", "♦", "♣"];
    const values = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"];

    function createDeck() {
        deck = [];
        for (let suit of suits) {
            for (let value of values) {
                deck.push({ suit, value });
            }
        }
        // Fisher-Yates Shuffle
        for (let i = deck.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [deck[i], deck[j]] = [deck[j], deck[i]];
        }
    }

    function getCardValue(card) {
        if (["J", "Q", "K"].includes(card.value)) return 10;
        if (card.value === "A") return 11;
        return parseInt(card.value);
    }

    function calculateScore(hand) {
        let score = 0;
        let aceCount = 0;

        for (let card of hand) {
            score += getCardValue(card);
            if (card.value === "A") aceCount++;
        }

        while (score > 21 && aceCount > 0) {
            score -= 10;
            aceCount--;
        }
        return score;
    }

    function renderCard(card, container) {
        const cardDiv = document.createElement("div");
        cardDiv.classList.add("card");
        
        // Add suit class for coloring
        if (card.suit === "♥") cardDiv.classList.add("hearts");
        else if (card.suit === "♦") cardDiv.classList.add("diamonds");
        else if (card.suit === "♠") cardDiv.classList.add("spades");
        else cardDiv.classList.add("clubs");

        cardDiv.innerHTML = `${card.value}<br>${card.suit}`;
        container.appendChild(cardDiv);
    }

    function updateUI(revealDealer = false) {
        // Clear board
        dealerCards.innerHTML = "";
        playerCards.innerHTML = "";

        // Render Player
        playerHand.forEach(card => renderCard(card, playerCards));
        playerScoreEl.innerText = `SCORE: ${calculateScore(playerHand)}`;

        // Render Dealer
        dealerHand.forEach((card, index) => {
            if (index === 0 && !revealDealer) {
                // Hidden Card
                const hiddenDiv = document.createElement("div");
                hiddenDiv.classList.add("card");
                hiddenDiv.style.borderColor = "#555";
                hiddenDiv.style.color = "#555";
                hiddenDiv.innerHTML = "?";
                dealerCards.appendChild(hiddenDiv);
            } else {
                renderCard(card, dealerCards);
            }
        });

        if (revealDealer) {
            dealerScoreEl.innerText = `SCORE: ${calculateScore(dealerHand)}`;
        } else {
            dealerScoreEl.innerText = `SCORE: ?`;
        }
    }

    function checkGameOver() {
        const pScore = calculateScore(playerHand);
        
        if (pScore > 21) {
            endGame("BUST! YOU LOSE.");
        } else if (pScore === 21 && playerHand.length === 2) {
            // Check if dealer also has BJ
            /* simplified for visualizer demo */
            endGame("BLACKJACK! YOU WIN!");
        }
    }

    function endGame(msg) {
        gameOver = true;
        messageEl.innerText = msg;
        btnHit.disabled = true;
        btnStand.disabled = true;
        btnDeal.disabled = false;
    }

    // --- ACTIONS ---
    function startNewGame() {
        gameOver = false;
        createDeck();
        playerHand = [deck.pop(), deck.pop()];
        dealerHand = [deck.pop(), deck.pop()];
        
        messageEl.innerText = "";
        btnHit.disabled = false;
        btnStand.disabled = false;
        btnDeal.disabled = true;
        
        updateUI(false);
        checkGameOver();
    }

    btnHit.addEventListener("click", () => {
        if (gameOver) return;
        playerHand.push(deck.pop());
        updateUI(false);
        checkGameOver();
    });

    btnStand.addEventListener("click", () => {
        if (gameOver) return;
        
        // Dealer plays
        while (calculateScore(dealerHand) < 17) {
            dealerHand.push(deck.pop());
        }

        updateUI(true); // Reveal hole card

        const pScore = calculateScore(playerHand);
        const dScore = calculateScore(dealerHand);

        if (dScore > 21) {
            endGame("DEALER BUSTS! YOU WIN.");
        } else if (dScore > pScore) {
            endGame("DEALER WINS.");
        } else if (pScore > dScore) {
            endGame("YOU WIN!");
        } else {
            endGame("PUSH (TIE).");
        }
    });

    btnDeal.addEventListener("click", startNewGame);
});