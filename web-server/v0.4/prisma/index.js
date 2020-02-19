const { prisma } = require('./generated/prisma-client')

// A `main` function so that we can use async/await
async function main() {

  // Create a new url
  const newUrl = await prisma.createUrl({ config: '{testing: true}', description: 'test url' })
  console.log(`Created new url: ${newUrl.description} (ID: ${newUrl.id})`)

  // Read all users from the database and print them to the console
  const allUrls = await prisma.urls()
  console.log(allUrls)
}

main().catch(e => console.error(e))
