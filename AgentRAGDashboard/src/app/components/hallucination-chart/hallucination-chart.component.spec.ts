import { ComponentFixture, TestBed } from '@angular/core/testing';

import { HallucinationChartComponent } from './hallucination-chart.component';

describe('HallucinationChartComponent', () => {
  let component: HallucinationChartComponent;
  let fixture: ComponentFixture<HallucinationChartComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [HallucinationChartComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(HallucinationChartComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
