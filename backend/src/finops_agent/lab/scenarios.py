from dataclasses import dataclass
from datetime import date, timedelta
from ..models import ClientProfile, BudgetPolicy, AllocationPolicy


@dataclass(frozen=True)
class Scenario:
    client_id: str
    name: str
    niche: str
    scale: float
    budget: float
    ai_service: str
    weekend: float

    def profile(self) -> ClientProfile:
        return ClientProfile(client_id=self.client_id, client_name=self.name, niche='SINTÉTICO · '+self.niche,
            budget_policy=BudgetPolicy(total_monthly_budget_usd=self.budget),
            allocation_policy=AllocationPolicy(mode='Showback',shared_cost_sub_accounts=['shared']))


SCENARIOS = {
    'lab-fintech': Scenario('lab-fintech','Nébula Payments · Laboratorio','Payments & AI',1,52000,'Vertex AI',.84),
    'lab-commerce': Scenario('lab-commerce','Mercado Aurora · Laboratorio','E-commerce',1.4,63000,'Amazon Bedrock',1.16),
}


def events(start: date) -> list[dict[str, str]]:
    def day(offset: int) -> str:
        return (start+timedelta(days=offset)).isoformat()
    return [dict(date=day(65),end=day(68),event='Campaña comercial aprobada; incremento temporal de tráfico web.',
                 scope='web'),
            dict(date=day(75),end=day(76),event='Despliegue del pipeline AI; validar costos con el equipo ML.',scope='ml')]


def truth(start: date) -> list[dict[str, str]]:
    return [dict(start=(start+timedelta(days=a)).isoformat(),end=(start+timedelta(days=b)).isoformat(),
                 kind=kind,expected=expected) for a,b,kind,expected in [
        (65,68,'planned_growth','Web sube 80%; contextualizar con campaña aprobada.'),
        (75,79,'ai_anomaly','AI sube 4x; vuelve a base desde día 80.'),
        (0,81,'missing_tags','Storage carece de owner y cost_center; reparación prospectiva desde día 82.'),
        (0,83,'commitment_waste','Capacidad contratada parcialmente ociosa; mejora desde día 84.'),
        (0,89,'commitment_opportunity','Web mantiene base On-Demand; evaluar compromisos excluyendo campaña.')]]
