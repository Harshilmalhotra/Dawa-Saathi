import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ScheduleCard } from './ScheduleCard';

describe('ScheduleCard', () => {
  it('renders the slot and medicine fixture', () => {
    render(<ScheduleCard slotIndex={0} lang="en" words={{before:'before food',after:'after food',with:'with food',empty:'empty stomach',any:'any time',tablet:'tablet',tablets:'tablets',daysRemaining:'days left',durationUnknown:'duration missing'}} medicines={[{id:'m1',drug_name:'Paracetamol',strength:'500 mg',frequency_code:'1-0-1-0',food_timing:'after_food'}]} />);
    expect(screen.getByText(/Morning/)).toBeTruthy();
    expect(screen.getByText(/Paracetamol/)).toBeTruthy();
  });
});
