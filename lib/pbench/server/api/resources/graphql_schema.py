from pbench.server.api.resources.models import MetadataModel
from pbench.server.api.resources.database import Database

import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyObjectType


# Define graphql types
class Metadata(SQLAlchemyObjectType):
    class Meta:
        model = MetadataModel
        interfaces = (relay.Node,)


class MetadataAttribute:
    id = graphene.ID
    user_id = graphene.ID()
    created = graphene.DateTime()
    updated = graphene.DateTime()
    config = graphene.String()
    description = graphene.String()


class CreateMetadataInput(graphene.InputObjectType, MetadataAttribute):
    pass


# mutations
class CreateMetadata(graphene.Mutation):
    metadata = graphene.Field(lambda: Metadata)
    ok = graphene.Boolean()

    class Arguments:
        input = CreateMetadataInput(required=True)

    @staticmethod
    def mutate(self, info, input):
        data = input
        metadata = MetadataModel(**data)
        Database.db_session.add(metadata)
        Database.db_session.commit()
        ok = True
        return CreateMetadata(metadata=metadata, ok=ok)


class Mutation(graphene.ObjectType):
    createMetadata = CreateMetadata.Field()


# Query
class Query(graphene.ObjectType):
    node = relay.Node.Field()

    metadata_by_id = graphene.List(Metadata, id=graphene.String())
    metadata_by_userid = graphene.List(Metadata, userid=graphene.String())

    @staticmethod
    def resolve_metadata_by_id(parent, info, **args):
        q = args.get("id")

        metadata_query = Metadata.get_query(info)
        return metadata_query.filter(MetadataModel.id == q).all()

    @staticmethod
    def resolve_metadata_by_userid(parent, info, **args):
        q = args.get("userid")

        metadata_query = Metadata.get_query(info)
        return metadata_query.filter(MetadataModel.user_id == q).all()


# schema
schema = graphene.Schema(query=Query, mutation=Mutation, types=[Metadata])
