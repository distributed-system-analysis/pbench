# Foreword

Pbench Dashboard Backend is a server side platform for storing and retrieving information to enable productivity within Pbench Dashboard. The platform allows for interaction between the React frontend and Postgres database by exposing a GraphQL API Server. This API server is powered by Prisma in order to enable high performance querying, a GUI client for visualizing queries, and a realtime event system for database event tracking.

# Scaffolding

```bash
├── generated
│   └── prisma-client
│       ├── index.d.ts        # typescript schema definition
│       ├── index.js          # Prisma client entrypoint
│       └── prisma-schema.js  # generated Prisma client schema
├── index.js                  # example script for writing data to the Prisma client
├── datamodel.prisma          # schema definitions for GraphQL data model
├── prisma.yml                # configuration for Prisma client
├── package.json              # project dependencies
├── README.md
```

# Server Installation

### Step 1: Install Docker

#### Install Docker CE

1.  Install the `dnf-plugins-core` package which provides the commands to manage
    your DNF repositories from the command line.

    ```bash
    $ sudo dnf -y install dnf-plugins-core
    ```

2.  Use the following command to set up the **stable** repository.

    ```bash
    $ sudo dnf config-manager \
        --add-repo \
        {{ download-url-base }}/docker-ce.repo
    ```

3.  Install the _latest version_ of Docker CE and containerd, or go to the next step to install a specific version:

    ```bash
    $ sudo dnf install docker-ce docker-ce-cli containerd.io
    ```

4.  Start Docker.

    ```bash
    $ sudo systemctl start docker
    ```

#### Step 2: Start the Prisma Server

Run the following command in the root of the project.

```bash
$ docker-compose up -d
```

#### Step 3: Install the Prisma CLI

Prisma services are managed with the [Prisma CLI](!alias-je3ahghip5). You can install it using `npm` (or `yarn`).

<Instruction>

Open your terminal and run the following command to install the Prisma CLI:

```
npm install -g prisma
# or
# yarn global add prisma
```

#### Step 4: Deploy the Prisma datamodel

```bash
$ prisma deploy
```
