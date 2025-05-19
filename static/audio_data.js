// Web Audio API를 사용한 소리 생성
let audioContext;

// 오디오 컨텍스트 초기화
function initAudioContext() {
    // 사용자 상호작용 이후 실행되어야 함
    if (!audioContext) {
        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            console.log("오디오 컨텍스트가 초기화되었습니다.");
        } catch (e) {
            console.error("오디오 컨텍스트 생성 오류:", e);
        }
    }
    return audioContext;
}

// 성공 소리 재생 (더 낮은 띵동 소리)
function playSuccessSound() {
    const context = initAudioContext();
    if (!context) return;
    
    try {
        // 첫 번째 음 (더 낮은 띵)
        const oscillator1 = context.createOscillator();
        const gainNode1 = context.createGain();
        
        oscillator1.type = 'sine';
        oscillator1.frequency.setValueAtTime(400, context.currentTime); // 훨씬 더 낮은 주파수로 변경
        
        gainNode1.gain.setValueAtTime(0, context.currentTime);
        gainNode1.gain.linearRampToValueAtTime(0.4, context.currentTime + 0.05);
        gainNode1.gain.linearRampToValueAtTime(0, context.currentTime + 0.4);
        
        oscillator1.connect(gainNode1);
        gainNode1.connect(context.destination);
        
        oscillator1.start();
        oscillator1.stop(context.currentTime + 0.4);
        
        // 두 번째 음 (동)
        const oscillator2 = context.createOscillator();
        const gainNode2 = context.createGain();
        
        oscillator2.type = 'sine';
        oscillator2.frequency.setValueAtTime(500, context.currentTime + 0.4); // 첫 번째보다 약간 높은 주파수
        
        gainNode2.gain.setValueAtTime(0, context.currentTime + 0.4);
        gainNode2.gain.linearRampToValueAtTime(0.4, context.currentTime + 0.45);
        gainNode2.gain.linearRampToValueAtTime(0, context.currentTime + 0.8);
        
        oscillator2.connect(gainNode2);
        gainNode2.connect(context.destination);
        
        oscillator2.start(context.currentTime + 0.4);
        oscillator2.stop(context.currentTime + 0.8);
        
        console.log("성공 소리가 재생되었습니다.");
    } catch (e) {
        console.error("성공 소리 재생 오류:", e);
    }
}

// 오류 소리 재생 (삐- 경고음)
function playErrorSound() {
    const context = initAudioContext();
    if (!context) return;
    
    try {
        // 삐- 소리 효과 생성
        const oscillator = context.createOscillator();
        const gainNode = context.createGain();
        
        // 더 높은 주파수의 정현파를 사용하여 경고음 생성
        oscillator.type = 'sawtooth'; // 톱니파를 사용하여 더 날카로운 경고음
        oscillator.frequency.setValueAtTime(700, context.currentTime); // 높은 주파수 삐- 소리
        
        // 음량 조절
        gainNode.gain.setValueAtTime(0, context.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.2, context.currentTime + 0.05); // 음량 최대치
        gainNode.gain.linearRampToValueAtTime(0.2, context.currentTime + 0.3); // 유지
        gainNode.gain.linearRampToValueAtTime(0, context.currentTime + 0.4); // 페이드 아웃
        
        oscillator.connect(gainNode);
        gainNode.connect(context.destination);
        
        oscillator.start();
        oscillator.stop(context.currentTime + 0.4);
        
        console.log("오류 소리가 재생되었습니다.");
    } catch (e) {
        console.error("오류 소리 재생 오류:", e);
    }
}

// 페이지 로드 시 사용자 상호작용 후 오디오 컨텍스트 초기화
document.addEventListener('click', function() {
    initAudioContext();
}, { once: true });

console.log("오디오 처리 모듈이 로드되었습니다.");