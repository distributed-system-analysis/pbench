# Pbench Dashboard 

Pbench Dashboard is the web-based platform for consuming indexed performance benchmark data. It provides data curation capabilities for the performance datasets.

The landing page is the browsing page where the user can view the list of public datasets. Those datasets can be filtered based on name and/or uploaded time.

![Browsing Page](assets/images/BrowsingPage.png)

Login button can be found on the right side of the Header. By clicking it, user will be redirected to Keycloak OIDC instance.

On logging in, the user can view the Overview Page which is the data curation page.
It has three components.

- New and Unmanaged Runs shows the newly created runs which can be Saved
- Saved Runs lists the saved runs which can be published to share with others
- Expiring Runs lists the runs with server deletion date < 20 days


![Overview](assets/images/Overview.png)


To view the profile details and the list of API keys associated with that account in the User Profile Page. By clicking on the dropdown next to the user name in the header, it will be navigated to the User Profile page. 

The user details are the fields of OIDC authentication token. The API Key section allows viewing and managing the set of Pbench Server API Keys the user has created with copy option. 

![User Profile](assets/images/UserProfile.png)

