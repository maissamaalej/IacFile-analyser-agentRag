package org.example.agentrag.Controller;

import lombok.RequiredArgsConstructor;
import org.example.agentrag.Dto.HallucinationPointDTO;
import org.example.agentrag.Dto.HallucinationStatsDto;
import org.example.agentrag.services.DashboardService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/dashboard")
@RequiredArgsConstructor
public class DashboardController {

    private final DashboardService dashboardService;

    @GetMapping("/hallucination")
    public HallucinationStatsDto hallucination() {

        return dashboardService.getHallucinationStats();

    }

    @GetMapping("/hallucination-chart")
    public List<HallucinationPointDTO> hallucinationChart() {

        return dashboardService.getHallucinationChart();

    }

}