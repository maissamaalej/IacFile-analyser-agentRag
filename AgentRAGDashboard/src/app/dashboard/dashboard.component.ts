import { Component, OnInit, AfterViewInit } from '@angular/core';
import { DashboardService, HallucinationStats } from '../services/dashboard.service';

import {
  Chart,
  registerables
} from 'chart.js';

Chart.register(...registerables);

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit, AfterViewInit {

  hallucinationRate: number = 0;
  averageScore: number = 0;
  totalEvaluations: number = 0;

  loading = false;

  chart!: Chart;

  constructor(
    private dashboardService: DashboardService
  ) {}

  ngOnInit(): void {

    this.loadMetrics();

  }

  ngAfterViewInit(): void {

    this.loadHallucinationChart();

  }

  loadMetrics(): void {

    this.loading = true;

    this.dashboardService
      .getHallucinationStats()
      .subscribe({

        next: (data: HallucinationStats) => {

          this.hallucinationRate = data.hallucinationRate;
          this.averageScore = data.averageScore;
          this.totalEvaluations = data.totalEvaluations;

          this.loading = false;

        },

        error: err => {

          console.error(err);

          this.loading = false;

        }

      });

  }

  loadHallucinationChart(): void {

    this.dashboardService
      .getHallucinationChart()
      .subscribe({

        next: (data: any[]) => {

          const labels = data.map(x => x.date);

          const values = data.map(x => x.rate);

          if (this.chart) {
            this.chart.destroy();
          }

          this.chart = new Chart("hallucinationChart", {

            type: 'line',

            data: {

              labels: labels,

              datasets: [

                {

                  label: 'Hallucination Rate %',

                  data: values,

                  fill: true,

                  tension: 0.4,

                  borderWidth: 3

                }

              ]

            },

            options: {

              responsive: true,

              plugins: {

                legend: {

                  display: true

                }

              },

              scales: {

                y: {

                  beginAtZero: true,

                  max: 100

                }

              }

            }

          });

        }

      });

  }

}