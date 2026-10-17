import { useEffect, useState } from 'react';

export type ScheduleMedicine = { id: string; drug_name?: string | null; strength?: string | null; frequency_code?: string | null; food_timing?: string | null; duration_days?: number | null; days_remaining?: number; duration_not_specified?: boolean; as_needed?: boolean };
const slotLabels = { en:['Morning ☀️','Afternoon 🌤️','Evening 🌇','Night 🌙'], hi:['सुबह ☀️','दोपहर 🌤️','शाम 🌇','रात 🌙'], mr:['सकाळ ☀️','दुपार 🌤️','संध्याकाळ 🌇','रात्र 🌙'] };

export function ScheduleCard({ slotIndex, medicines, lang, words }: { slotIndex: number; medicines: ScheduleMedicine[]; lang: 'en'|'hi'|'mr'; words: Record<string,string> }) {
  const [hasVoice, setHasVoice] = useState(false);
  useEffect(() => {
    const check = () => setHasVoice(typeof window !== 'undefined' && 'speechSynthesis' in window && window.speechSynthesis.getVoices().length > 0);
    check();
    window.speechSynthesis?.addEventListener?.('voiceschanged', check);
    return () => window.speechSynthesis?.removeEventListener?.('voiceschanged', check);
  }, []);
  const selected = medicines.filter(m => !m.as_needed && (m.frequency_code?.split('-')[slotIndex] ?? '0') !== '0');
  const read = () => {
    if (!hasVoice) return;
    const speech = new SpeechSynthesisUtterance(selected.map(m => `${m.drug_name ?? ''} ${m.strength ?? ''} ${m.food_timing?.replace('_', ' ') ?? ''}`).join(', '));
    speech.lang = lang === 'mr' ? 'mr-IN' : lang === 'hi' ? 'hi-IN' : 'en-IN';
    window.speechSynthesis.speak(speech);
  };
  const food:Record<string,string>={before_food:words.before,after_food:words.after,with_food:words.with,empty_stomach:words.empty,any:words.any};
  const title=slotLabels[lang][slotIndex];
  return <section className="card"><h2>{title}</h2>{selected.map(m => { const amount=m.frequency_code?.split('-')[slotIndex]??''; const duration=m.duration_not_specified?words.durationUnknown:`${m.days_remaining??0} ${words.daysRemaining}`; return <p key={m.id}>💊 {m.drug_name} {m.strength} · {words.amount}: {amount} · {food[m.food_timing??'any']} · {duration}</p>; })}{hasVoice&&<button aria-label={`Read ${title}`} onClick={read}>🔊</button>}</section>;
}
