import asyncio
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastapi import FastAPI, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.context import ConstructionContext
from app.core.security import get_construction_context
from app.domain.record_scope import ProjectScope
from app.infrastructure.clients.erp_construction import ErpConstructionClient
from app.infrastructure.database.models import ConstructionProject, ConstructionUnit, ConstructionUnitSale, OutboxEvent
from app.infrastructure.database.session import get_session
from app.infrastructure.events.integration_jobs import relay_integration_once
from app.presentation.routes.construction_projects import router


async def run(config):
    ids = {key: UUID(value) for key, value in config['ids'].items()}
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        database = await session.scalar(text('SELECT current_database()'))
        assert database.startswith('test_unit_transfer_http_'), database
        source_project = ConstructionProject(id=ids['source_project'], company_id=ids['company_id'],
                                             code='HTTP-SOURCE', name='Source project', status='active')
        target_project = ConstructionProject(id=ids['target_project'], company_id=ids['company_id'],
                                             code='HTTP-TARGET', name='Target project', status='active')
        foreign_project = ConstructionProject(id=ids['foreign_project'], company_id=ids['foreign_company'],
                                              code='HTTP-FOREIGN', name='Foreign project', status='active')
        session.add_all([source_project, target_project, foreign_project])
        await session.flush()
        source = ConstructionUnit(id=ids['source_unit'], company_id=ids['company_id'], project_id=source_project.id,
                                  code='HTTP-SOURCE', unit_type='house', description='Source unit', status='sold',
                                  buyer_person_id=ids['person_id'], sale_price=Decimal('5500'),
                                  sold_at=datetime(2024, 3, 19, 12, tzinfo=UTC),
                                  analytic_cost_center_id=ids['source_center'], external_contract_id=ids['contract'])
        target = ConstructionUnit(id=ids['target_unit'], company_id=ids['company_id'], project_id=target_project.id,
                                  code='HTTP-TARGET', unit_type='house', description='Target unit', status='available',
                                  analytic_cost_center_id=ids['target_center'])
        foreign = ConstructionUnit(id=ids['foreign_unit'], company_id=ids['foreign_company'],
                                   project_id=foreign_project.id, code='HTTP-FOREIGN', unit_type='house',
                                   description='Foreign unit', status='available', analytic_cost_center_id=ids['target_center'])
        session.add_all([source, target, foreign])
        await session.flush()
        sale = ConstructionUnitSale(id=ids['source_sale'], company_id=ids['company_id'], unit_id=source.id,
                                    sequence=1, status='ACTIVE', source='NATIVE', buyer_person_id=ids['person_id'],
                                    sale_price=Decimal('5500'), sold_at=source.sold_at,
                                    external_contract_id=ids['contract'])
        session.add(sale)
        await session.flush()
        source.current_sale_id = sale.id
        await session.commit()

    app = FastAPI()
    app.include_router(router)

    async def session_dependency():
        async with factory() as session:
            yield session

    async def context(request: Request):
        actor = request.headers.get('X-Test-Actor', 'full')
        scope = ProjectScope.limited_to([ids['source_project'], ids['target_project']])
        permissions = {'construction_units': 15, 'receivable': 15}
        user = ids['user_id']
        if actor == 'restricted':
            scope = ProjectScope.limited_to([ids['source_project']])
            user = ids['restricted_user']
        elif actor == 'no-finance':
            permissions['receivable'] = 1
            user = ids['no_finance_user']
        return ConstructionContext(company_id=ids['company_id'], user_id=user, person_id=ids['person_id'],
                                   feature_permissions=permissions, project_scope=scope)

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_construction_context] = context
    path = f"/construction/units/{ids['source_unit']}/transfer"
    request = {'target_unit_id': str(ids['target_unit']), 'source_sale_id': str(ids['source_sale']),
               'reason': 'HTTP integration transfer with registered bank slip'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://construction.test') as client:
        restricted = await client.post(path + '/preview', json=request, headers={'X-Test-Actor': 'restricted'})
        assert restricted.status_code == 404, restricted.text
        no_finance = await client.post(path + '/preview', json=request, headers={'X-Test-Actor': 'no-finance'})
        assert no_finance.status_code == 403, no_finance.text
        foreign = await client.post(path + '/preview', json={**request, 'target_unit_id': str(ids['foreign_unit'])})
        assert foreign.status_code == 404, foreign.text
        preview = await client.post(path + '/preview', json=request)
        assert preview.status_code == 200, preview.text
        assert Decimal(preview.json()['financial']['paid_amount']) == Decimal('1000')
        confirmed = await client.post(path, json=request)
        assert confirmed.status_code == 200, confirmed.text
        transfer_id = confirmed.json()['transfer_id']
        assert confirmed.json()['status'] == 'pending'
        blocked = await client.post(path + '/preview', json=request)
        assert blocked.status_code == 400, blocked.text
        assert blocked.json()['detail']['error_code'] == 'CONSTRUCTION_UNIT_TRANSFER_PENDING'
        async with httpx.AsyncClient(base_url=settings.erp_api_url, trust_env=False) as erp:
            payment = await erp.post('/test/receive', headers={'X-Service-Key': settings.erp_service_key,
                'X-Company-ID': str(ids['company_id']), 'X-User-ID': str(ids['user_id'])})
            assert payment.status_code == 200, payment.text
        async with factory() as session:
            assert await relay_integration_once(session, ErpConstructionClient())
        async with factory() as session:
            event = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == UUID(transfer_id)))
            assert event.status == ('failed' if config['lost_response'] else 'published'), event.last_error
            original_payload = event.payload
        if config['lost_response']:
            retry_path = f"/construction/units/{ids['source_unit']}/transfers/{transfer_id}/retry"
            retry = await client.post(retry_path, headers={'X-Test-Actor': 'restricted'})
            assert retry.status_code == 404, retry.text
            retry = await client.post(retry_path)
            assert retry.status_code == 200, retry.text
            async with factory() as session:
                assert await relay_integration_once(session, ErpConstructionClient())
        history = await client.get(f"/construction/units/{ids['target_unit']}/transfers")
        assert history.status_code == 200, history.text
        assert len(history.json()['items']) == 1

    async with factory() as session:
        event = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == UUID(transfer_id)))
        sale = await session.get(ConstructionUnitSale, ids['source_sale'])
        source = await session.get(ConstructionUnit, ids['source_unit'])
        target = await session.get(ConstructionUnit, ids['target_unit'])
        assert event.status == 'published' and event.last_error is None
        assert event.event_id == UUID(transfer_id) and event.payload['target_sale_id'] == original_payload['target_sale_id']
        assert sale.status == 'TRANSFERRED' and sale.paid_amount == Decimal('1500')
        assert source.status == 'available' and source.current_sale_id is None
        assert target.status == 'sold' and target.current_sale_id == UUID(event.payload['target_sale_id'])
        assert target.external_contract_id is not None and target.external_contract_id != ids['contract']
        histories = (await session.execute(text(
            'SELECT unit_id, included_at, excluded_at FROM construction.unit_buyer_history WHERE company_id=:company'
        ), {'company': ids['company_id']})).all()
        assert len(histories) == 2
        result = {'event_id': transfer_id, 'payload': event.payload, 'status': event.status,
                  'paid_amount': str(sale.paid_amount), 'target_contract': str(target.external_contract_id),
                  'restricted_status': restricted.status_code, 'foreign_status': foreign.status_code,
                  'no_finance_status': no_finance.status_code}
    await engine.dispose()
    return result


if __name__ == '__main__':
    print('TRANSFER_HTTP_RESULT=' + json.dumps(asyncio.run(run(json.load(sys.stdin)))))
