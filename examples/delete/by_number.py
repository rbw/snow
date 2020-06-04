from snow.schemas.table import IncidentSchema as Incident


async def main(app):
    async with app.get_table(Incident) as inc:
        # Delete by number
        await inc.delete(Incident.number == "INC0010341")
